"""Release invariants and independently generated camera-image measurements."""

import copy
import math

import numpy as np
import pytest

from coldatomlab.vortex import Vortex, scales, verify_export
from coldatomlab.vortex_imaging import acquire, core

CAMERA = dict(
    axis="z",
    binning=1,
    fwhm_um=0,
    saturation=1,
    exposure_us=5,
    efficiency=0.8,
    read_noise=1,
    noise=False,
    seed=17,
    roi_um=8,
    strip_um=4,
)


def analytic(sim, t, charge=1):
    x, y, z = sim.X, sim.Y, sim.Z
    radial = 1 + 1j * t
    axial = 1 + 2j * t
    p = (
        2**0.25
        / math.pi**0.75
        * np.exp(-(x * x + y * y) / (2 * radial) - z * z / axial)
        / (radial * np.sqrt(axial))
    )
    if charge:
        p = p * (x + 1j * charge * y) / radial
    return p


@pytest.mark.parametrize("charge", [-1, 0, 1])
def test_exact_released_field_and_conserved_observables(charge):
    s = Vortex(dict(n=64, length=24, atoms=1000, charge=charge))
    s.release()
    d0 = s.diagnostics()
    s.advance(500)
    d = s.diagnostics()
    # Infinite-space analytic tails differ from the periodic box (~8e-5).
    # Independent box/grid refinement is in vortex_release_check.py.
    assert np.linalg.norm(s.psi - analytic(s, 2, charge)) * s.dx**1.5 < 9e-5
    assert d["norm"] == pytest.approx(1, abs=1e-11)
    assert d["energy"] == pytest.approx(d0["energy"], abs=1e-10)
    assert d["energy"] == pytest.approx(1 + 0.5 * abs(charge), abs=2e-6)
    assert d["lz"] == pytest.approx(charge, abs=2e-6)
    assert d["widths"] == pytest.approx(
        [math.sqrt((1 + abs(charge)) * 2.5)] * 2 + [math.sqrt(17) / 2], rel=2e-5
    )
    assert d["edge_probability"] < 1e-6


def packed(p):
    return np.stack([p.real, p.imag], axis=-1).ravel().tolist()


@pytest.fixture(scope="module")
def released():
    s = Vortex(dict(n=64, length=24, atoms=1000))
    s.release()
    s.advance(500)
    return dict(config=s.config, field=packed(s.psi), scales=scales())


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_projection_total_and_axis_measurement(released, axis):
    image, measurements = acquire(released, CAMERA | dict(axis=axis))
    assert image["model_total_atoms"] == pytest.approx(1000, rel=1e-10)
    assert image["density"] == pytest.approx(image["truth_density"], rel=1e-10, abs=1e-10)
    assert measurements["camera"]["available"] == (axis == "z")
    if axis == "z":
        m = measurements["camera"]
        assert math.hypot(m["x_um"], m["y_um"]) < 0.01
        assert 0.89 < m["contrast"] < 0.92 and 3.4 < m["diameter_um"] < 3.7


@pytest.mark.parametrize(
    "axis,expected", [("z", (0.6, -0.8)), ("y", (0.6, 0.3)), ("x", (-0.8, 0.3))]
)
def test_projection_orientation(axis, expected):
    s = Vortex(dict(n=32, width=1, atoms=1000))
    psi = np.exp(-((s.X - 0.6) ** 2 / 2 + (s.Y + 0.8) ** 2 / 3 + (s.Z - 0.3) ** 2))
    psi /= np.sqrt(np.sum(psi**2) * s.dx**3)
    image, _ = acquire(
        dict(config=s.config, scales=scales(), field=packed(psi)), CAMERA | dict(axis=axis)
    )
    density = image["truth_density"]
    x = image["x_um"]
    center = [
        (density * x[None, :]).sum() / density.sum(),
        (density * x[:, None]).sum() / density.sum(),
    ]
    assert np.array(center) / scales()["length_um"] == pytest.approx(expected, abs=1e-6)


def test_optical_blur_and_pixel_averaging(released):
    ideal, m = acquire(released, CAMERA)
    blurred, b = acquire(released, CAMERA | dict(fwhm_um=3))
    assert b["camera"]["available"] and 0.35 < b["camera"]["contrast"] < 0.5
    assert b["camera"]["contrast"] < m["camera"]["contrast"]
    binned, _ = acquire(released, CAMERA | dict(binning=2))
    assert len(binned["x_um"]) == len(ideal["x_um"]) // 2
    assert binned["pixel_um"] == pytest.approx(2 * ideal["pixel_um"])
    assert blurred["atoms_frame"].shape == ideal["atoms_frame"].shape


def test_noise_reproducible_and_position_accuracy(released):
    positions = []
    contrasts = []
    first = None
    for seed in range(12):
        image, m = acquire(released, CAMERA | dict(noise=True, seed=seed))
        if seed == 0:
            first = image["atoms_frame"].copy()
        if m["camera"]["available"]:
            positions.append(math.hypot(m["camera"]["x_um"], m["camera"]["y_um"]))
            contrasts.append(m["camera"]["contrast"])
    again, _ = acquire(released, CAMERA | dict(noise=True, seed=0))
    assert np.array_equal(first, again["atoms_frame"])
    assert len(positions) >= 10 and max(positions) < 0.5
    assert 0.8 < np.mean(contrasts) < 1


def test_invalid_and_false_density_dip():
    x = np.linspace(-8, 8, 65)
    X, Y = np.meshgrid(x, x)
    a = np.exp(-(X * X + Y * Y) / 12)
    assert not core(a, x, 7)["available"]
    a[32, 32] = np.nan
    assert not core(a, x, 7)["available"]
    assert not core(np.zeros_like(a), x, 7)["available"]


@pytest.mark.parametrize("position", [(0.35, -0.7), (-0.6, 0.4)])
def test_image_only_offset_core(position):
    x = np.arange(-12, 12, 0.25)
    X, Y = np.meshgrid(x - position[0], x - position[1])
    r2 = X * X + Y * Y
    m = core(r2 * np.exp(-r2 / 12), x, 9)
    assert m["available"]
    assert (m["x_um"], m["y_um"]) == pytest.approx(position, abs=0.025)


@pytest.mark.parametrize(
    "config", [dict(atoms=999), dict(atoms=1000.5), dict(atoms=1000, g=1000), dict(tof_duration=0)]
)
def test_invalid_release_parameters(config):
    from coldatomlab.vortex import validate

    with pytest.raises(ValueError):
        validate(config)


def test_release_timing_replay_and_protocol_tampering():
    s = Vortex(dict(n=32, width=1, tof_duration=0.1))
    initial = s.initial.copy()
    rows = [s.diagnostics()]
    s.advance(10)
    s.release()
    rows.append(s.diagnostics())
    s.advance(25)
    rows.append(s.diagnostics())
    data = dict(
        schema="coldatomlab-vortex-v2",
        version="0.17.0",
        config=s.config,
        scales=scales(),
        array_order="x,y,z interleaved real,imag",
        initial=packed(initial),
        field=packed(s.psi),
        steps=35,
        release_step=10,
        history=rows,
    )
    assert verify_export(data)["verified"]
    for key, value in [("release_step", None), ("release_step", -1), ("release_step", 36)]:
        bad = copy.deepcopy(data)
        bad[key] = value
        with pytest.raises(ValueError):
            verify_export(bad)
    bad = copy.deepcopy(data)
    bad["history"][-1]["widths"][0] *= 1.2
    with pytest.raises(ValueError):
        verify_export(bad)

    from coldatomlab.vortex_imaging import verify_export as verify_image_export

    image, measurements = acquire(data, CAMERA)
    image["camera"] = CAMERA.copy()
    export = dict(
        schema="coldatomlab-vortex-image-v1",
        version="0.17.0",
        camera_model="rb87-browser-camera-v1",
        source=data,
        image=image,
        measurements=measurements,
    )
    assert verify_image_export(export)["verified"]
    bad = copy.deepcopy(export)
    bad["image"]["atoms_frame"][16, 16] += 10
    with pytest.raises(ValueError):
        verify_image_export(bad)
    bad = copy.deepcopy(export)
    bad["measurements"]["camera"]["x_um"] = 10
    with pytest.raises(ValueError):
        verify_image_export(bad)
