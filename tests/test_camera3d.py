from dataclasses import asdict

import numpy as np
import pytest

from coldatomlab.camera3d import CameraRNG, acquire_reference, fit_profile, project, verify_camera
from coldatomlab.interferometry3d import gaussian_pair
from coldatomlab.solver3d import Config3D

SETTINGS = dict(
    axis="z",
    binning=1,
    fwhm_um=0,
    saturation=1,
    exposure_us=5,
    efficiency=0.8,
    read_noise=1,
    noise=False,
    seed=17,
    roi_um=12,
    strip_um=4,
)


@pytest.fixture
def source():
    c = Config3D(
        n=64,
        length=32,
        atoms=2000,
        experiment="pair",
        scattering_nm=0,
        relative_phase=0.7,
        duration=3,
    )
    x = (np.arange(c.n) - c.n // 2) * c.length / c.n
    psi = gaussian_pair(c, x, 3)
    return dict(config=asdict(c), psi_real=psi.real, psi_imag=psi.imag)


def test_projection_orientation_and_atom_integrals(source):
    c = Config3D(**source["config"])
    x = (np.arange(c.n) - c.n // 2) * c.length / c.n
    X, Y, Z = np.meshgrid(x, x, x, indexing="ij")
    density = np.exp(-((X - 2) ** 2 + (Y + 1) ** 2 / 2 + (Z - 0.5) ** 2 / 3))
    density /= density.sum() * (c.length / c.n) ** 3
    source.update(psi_real=np.sqrt(density), psi_imag=np.zeros_like(density))
    for axis, centers in [("z", [2, -1]), ("y", [2, 0.5]), ("x", [-1, 0.5])]:
        image, coords, axes = project(source, axis)
        pitch = coords[1] - coords[0]
        assert image.sum() * pitch**2 == pytest.approx(c.atoms, rel=1e-12)
        assert axes == [a for a in "xyz" if a != axis]
        assert (image.sum(axis=0) @ coords / image.sum()) == pytest.approx(
            centers[0] * c.scales["length_um"], abs=1e-6
        )
        assert (image.sum(axis=1) @ coords / image.sum()) == pytest.approx(
            centers[1] * c.scales["length_um"], abs=1e-6
        )


@pytest.mark.parametrize("phase", [0, 0.7, -1.2, 3.0])
def test_blind_image_fit(phase):
    x = np.linspace(-12, 12, 97)
    y = np.exp(-x * x / 72) * (1 + 0.65 * np.cos(2 * np.pi * x / 5 - phase))
    fit = fit_profile(x, y)
    assert fit["available"]
    assert abs(np.angle(np.exp(1j * (fit["phase"] - phase)))) < 0.01
    assert fit["spacing"] == pytest.approx(5, rel=0.01)
    assert fit["contrast"] == pytest.approx(0.65, abs=0.02)
    assert not fit_profile(x, np.exp(-x * x / 72))["available"]
    assert not fit_profile(x[::8], y[::8])["available"]
    assert not fit_profile(x, y, np.ones(len(x)))["available"]


def test_ideal_blur_binning_and_unresolved_views(source):
    before = source["psi_real"].copy()
    ideal = acquire_reference(source, SETTINGS)
    assert np.max(abs(ideal["density"] - ideal["truth_density"])) < 1e-12
    assert ideal["atoms_roi"] == pytest.approx(ideal["truth_atoms_roi"], rel=1e-12)
    assert ideal["measured"]["available"]
    assert ideal["measured"]["phase"] == pytest.approx(0.7, abs=0.03)
    blurred = acquire_reference(source, SETTINGS | {"fwhm_um": 4})
    assert blurred["measured"]["contrast"] < ideal["measured"]["contrast"]
    assert not acquire_reference(source, SETTINGS | {"fwhm_um": 8})["measured"]["available"]
    assert not acquire_reference(source, SETTINGS | {"axis": "x"})["measured"]["available"]
    binned = acquire_reference(source, SETTINGS | {"binning": 2})
    assert binned["pixel_um"] == pytest.approx(2 * ideal["pixel_um"])
    # Integrate transmitted intensity before nonlinear inversion: density binning is different.
    assert np.max(abs(binned["density"] - binned["truth_density"])) > 0.01
    assert np.array_equal(source["psi_real"], before)


@pytest.mark.parametrize("mean", [0.2, 12, 30, 400])
def test_photon_noise_statistics(mean):
    rng = CameraRNG(182)
    values = np.array([rng.poisson(mean) for _ in range(30000)])
    assert abs(values.mean() - mean) < 5 * np.sqrt(mean / len(values))
    assert values.var() == pytest.approx(mean, rel=0.04)


def test_seed_read_noise_and_replay_tampering(source):
    c = SETTINGS | {"noise": True}
    image = acquire_reference(source, c)
    other = acquire_reference(source, c)
    assert np.array_equal(image["atoms_frame"], other["atoms_frame"])
    assert not np.array_equal(
        image["atoms_frame"], acquire_reference(source, c | {"seed": 18})["atoms_frame"]
    )
    assert image["dark_frame"].mean() == pytest.approx(100, abs=0.06)
    assert image["dark_frame"].var() == pytest.approx(1, rel=0.07)
    assert np.any(image["density"] < 0)
    record = dict(camera_model="rb87-browser-camera-v1", source=source, image=image | {"camera": c})
    assert verify_camera(record)["camera_verified"]
    record["image"]["atoms_frame"][0, 0] += 1
    with pytest.raises(ValueError, match="atoms_frame"):
        verify_camera(record)
    record["image"]["atoms_frame"][0, 0] -= 1
    record["image"]["axes"] = ["x", "z"]
    with pytest.raises(ValueError, match="axes"):
        verify_camera(record)


def test_dark_pixels_remain_invalid(source):
    source["config"]["atoms"] = 200000
    image = acquire_reference(source, SETTINGS | {"noise": True, "exposure_us": 0.1})
    assert image["invalid_roi_pixels"] > 0
    assert image["atoms_roi"] is None
    assert not image["measured"]["available"]


@pytest.mark.parametrize(
    "setting", [{"binning": 3}, {"axis": "q"}, {"seed": -1}, {"exposure_us": 0}]
)
def test_invalid_settings(source, setting):
    with pytest.raises(ValueError):
        acquire_reference(source, SETTINGS | setting)
