from dataclasses import replace

import numpy as np
import pytest

from coldatomlab.imaging import Camera, blur_transmission, capture, form_image, transmission
from coldatomlab.physical import Physical
from coldatomlab.replay import verify_export
from coldatomlab.solver import Config, Solver


def scene(n=128):
    p = Physical()
    x = (np.arange(n) - n / 2) * 32 / n
    xx, yy = np.meshgrid(x * p.scales()["length_um"], x * p.scales()["length_um"])
    rho = np.exp(-(xx**2 + yy**2) / (2 * 8**2)) * (1 + 0.8 * np.cos(2 * np.pi * xx / 6))
    rho /= rho.sum() * (32 / n) ** 2
    return rho, x, p


def test_saturated_beer_lambert_inversion():
    od = np.linspace(0, 100, 200)
    for s in (0.001, 0.1, 1, 10):
        t = transmission(od, s)
        np.testing.assert_allclose(-np.log(t) + s * (1 - t), od, atol=1e-12)
    np.testing.assert_allclose(transmission(od, 0), np.exp(-od), atol=1e-14)


def test_noiseless_camera_recovers_counts_and_moments_without_oracle():
    rho, x, p = scene()
    result = form_image(rho, x, p, Camera(binning=1, fwhm_um=0, noise=False, saturation=3))
    density = np.array(result["density"])
    np.testing.assert_allclose(density, rho * p.atoms / p.scales()["length_um"] ** 2, atol=1e-12)
    for key in ("atoms", "width_x", "width_y", "fringe_spacing", "fringe_contrast"):
        assert result["measured"][key] == pytest.approx(result["truth"][key], abs=1e-10)


def test_psf_broadens_an_absorption_deficit_and_has_no_wraparound():
    x = np.arange(128) - 64
    xx, yy = np.meshgrid(x, x)
    deficit = np.exp(-(xx**2 + yy**2) / (2 * 5**2)) * 0.01
    blurred = 1 - blur_transmission(1 - deficit, 3)
    assert blurred.sum() == pytest.approx(deficit.sum(), rel=1e-10)
    assert (blurred * xx**2).sum() / blurred.sum() == pytest.approx(25 + 9, rel=1e-6)
    edge = np.ones((64, 64))
    edge[32, 0] = 0
    image = blur_transmission(edge, 2)
    assert image[32, -1] == pytest.approx(1, abs=1e-14)


def test_resolution_and_pixel_size_destroy_resolved_fringes():
    rho, x, p = scene(256)
    sharp = form_image(rho, x, p, Camera(binning=1, fwhm_um=0, noise=False))
    mild = form_image(rho, x, p, Camera(binning=1, fwhm_um=2, noise=False))
    blurred = form_image(rho, x, p, Camera(binning=1, fwhm_um=10, noise=False))
    coarse = form_image(rho, x, p, Camera(binning=16, fwhm_um=0, noise=False, strip_um=10))
    assert sharp["measured"]["fringe_spacing"] == pytest.approx(6, abs=0.4)
    assert mild["measured"]["fringe_contrast"] < sharp["measured"]["fringe_contrast"] - 0.15
    assert blurred["measured"]["fringe_spacing"] is None
    assert coarse["measured"]["fringe_spacing"] is None
    assert blurred["measured"]["atoms"] < blurred["truth"]["atoms"]


def test_photon_statistics_seed_and_exposure_scaling():
    rho, x, p = scene()
    rho[:] = 0
    c = Camera(binning=1, read_noise=0, exposure_us=20)
    a = form_image(rho, x, p, c)
    ref = np.asarray(a["reference_frame"]) - 100
    atoms = np.asarray(a["atoms_frame"]) - 100
    mean = a["expected_reference_e"]
    assert ref.mean() == pytest.approx(mean, rel=0.03)
    assert ref.var() == pytest.approx(mean, rel=0.05)
    assert abs(np.corrcoef(ref.ravel(), atoms.ravel())[0, 1]) < 0.04
    assert form_image(rho, x, p, c) == a
    assert form_image(rho, x, p, replace(c, seed=18))["atoms_frame"] != a["atoms_frame"]
    doubled = form_image(rho, x, p, replace(c, exposure_us=40))
    assert doubled["expected_reference_e"] == pytest.approx(2 * mean)
    assert np.std(np.array(doubled["reference_frame"]) / 2) < np.std(ref)


def test_low_counts_mask_and_roi_are_explicit():
    rho, x, p = scene()
    image = form_image(rho, x, p, Camera(exposure_us=0.1, saturation=0.001))
    assert image["invalid_roi_pixels"] > 0
    assert image["measured"]["atoms"] is None
    assert image["measured"]["width_x"] is None
    assert image["measured"]["fringe_spacing"] is None
    small = form_image(rho, x, p, Camera(roi_um=4, noise=False))
    assert small["truth"]["atoms"] < small["model_total_atoms"] * 0.5
    assert any("ROI excludes" in w for w in small["warnings"])


def test_read_noise_and_shared_dark_covariance():
    rho, x, p = scene()
    rho[:] = 0
    image = form_image(rho, x, p, Camera(binning=1, read_noise=5, exposure_us=20))
    dark = np.array(image["dark_frame"])
    a = np.array(image["atoms_frame"]) - dark
    r = np.array(image["reference_frame"]) - dark
    assert dark.var() == pytest.approx(25, rel=0.05)
    assert a.var() == pytest.approx(image["expected_reference_e"] + 50, rel=0.05)
    assert np.cov(a.ravel(), r.ravel())[0, 1] == pytest.approx(25, rel=0.1)


def test_capture_does_not_evolve_or_mutate_and_replays_raw_frames():
    s = Solver(Config(experiment="double", n=64, physical=Physical()))
    s.advance(5)
    before = s.export()
    shot = capture(s, Camera(noise=True, seed=18, read_noise=2, strip_um=5))
    assert s.export() == before
    assert verify_export(shot)["camera_replayed"]
    other = capture(s, Camera(noise=False, strip_um=5))
    comparison = {"schema": "coldatomlab-camera-comparison-v1", "reference": shot, "current": other}
    assert verify_export(comparison)["reference"]["camera_replayed"]
    shot["image"]["atoms_frame"][0][0] += 1
    with pytest.raises(ValueError, match="Camera replay differs"):
        verify_export(shot)
    other["source"]["x"][0] += 1
    with pytest.raises(ValueError, match="coordinates"):
        verify_export(other)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"binning": True},
        {"binning": 3},
        {"noise": 1},
        {"seed": -1},
        {"fwhm_um": float("nan")},
        {"efficiency": 0},
        {"exposure_us": 0},
        {"roi_um": -2},
        {"read_noise": -1},
    ],
)
def test_bad_camera_settings(kwargs):
    with pytest.raises(ValueError):
        Camera(**kwargs)


def test_requires_physical_rb_and_resolved_roi():
    rho, x, p = scene(64)
    for physical in (None, Physical(species="custom", mass_u=23)):
        with pytest.raises(ValueError, match="Rb-87"):
            form_image(rho, x, physical, Camera())
    with pytest.raises(ValueError, match="8 camera pixels"):
        form_image(rho, x, p, Camera(binning=16))
    with pytest.raises(ValueError, match="ROI"):
        form_image(rho, x, p, Camera(binning=8, roi_um=1))
