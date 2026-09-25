import copy
from dataclasses import replace

import numpy as np
import pytest

from coldatomlab.replay import verify_export
from coldatomlab.solver3d import Config3D, Solver3D, tf_reference


def finish(s):
    while not s.complete and not s.warning:
        s.advance(20)
    return s.diagnostics()


def test_3d_gaussian_ground_release_and_projection_units():
    c = Config3D(n=48, length=24, scattering_nm=0, duration=2)
    s = Solver3D(c)
    w = c.omegas
    assert s.diagnostics()["energy"] == pytest.approx(w.sum() / 2, rel=1e-9)
    # At dx=0.5 the sampled oscillator has a small spectral cutoff residual.
    assert s.preparation["relative_stationary_residual"] < 1e-6
    initial = s.psi.copy()
    s.release()
    d = finish(s)
    exact = np.sqrt((1 + w * w * s.time**2) / (2 * w))
    assert np.allclose(d["widths"], exact, rtol=1e-5)
    assert abs(d["norm"] - 1) < 1e-10
    x, y, z = np.meshgrid(s.x, s.x, s.x, indexing="ij")
    density = np.ones_like(x)
    for axis, o in zip((x, y, z), w):
        variance = (1 + o * o * s.time**2) / (2 * o)
        density *= np.exp(-(axis**2) / (2 * variance)) / np.sqrt(2 * np.pi * variance)
    assert np.max(abs(abs(s.psi) ** 2 - density)) < 1e-8
    shot = s.snapshot()
    for column in shot["columns"]:
        assert np.sum(column) * s.dx**2 == pytest.approx(1, abs=1e-10)
        physical = np.asarray(column) * c.atoms / c.scales["length_um"] ** 2
        assert physical.sum() * (s.dx * c.scales["length_um"]) ** 2 == pytest.approx(c.atoms)
    assert np.allclose(shot["slices"][1], abs(s.psi[:, c.n // 2, :].T) ** 2)
    s.reset()
    assert np.array_equal(s.psi, initial)
    assert s.release_step is None and not s.complete


@pytest.fixture(scope="module")
def interacting():
    return Solver3D(Config3D(n=32, length=16, atoms=2000, duration=0.5))


def test_3d_stationarity_and_real_time_convergence(interacting):
    s = copy.deepcopy(interacting)
    assert s.preparation["relative_stationary_residual"] < 2e-6
    widths = s.diagnostics()["widths"]
    held = finish(s)
    assert np.allclose(held["widths"], widths, rtol=2e-5)
    errors = []
    for dt in (0.008, 0.004, 0.002):
        s = copy.deepcopy(interacting)
        s.config = replace(s.config, dt=dt, duration=0.48)
        s.kinetic_step = np.exp(-0.5j * dt * s.k2)
        s.release()
        e0 = s.diagnostics()["energy"]
        d = finish(s)
        assert abs(d["norm"] - 1) < 1e-11
        errors.append(abs(d["energy"] - e0))
    assert errors[0] > 3.8 * errors[1] and errors[1] > 3.8 * errors[2]


def test_3d_export_replay_release_and_reject_tampering(interacting):
    s = copy.deepcopy(interacting)
    s.advance(7)
    s.release()
    s.advance(13)
    data = s.export()
    assert verify_export(data)["max_wavefunction_error"] < 1e-13
    data["psi_real"][0][0][0] += 0.01
    with pytest.raises(ValueError, match="differs"):
        verify_export(data)


def test_3d_tf_reference_invariant_and_symmetry():
    c = Config3D(fx_hz=30, fy_hz=30, fz_hz=30)
    ref = tf_reference(c, np.linspace(0, 4, 51))
    assert np.max(abs(np.array(ref["scaling_energy_invariant"]) - 1)) < 1e-8
    assert np.allclose(np.array(ref["scales"])[:, 0], np.array(ref["scales"])[:, 2])
    assert tf_reference(replace(c, scattering_nm=0), [0, 1]) is None


def test_3d_boundary_stop_and_invalid_inputs():
    s = Solver3D(Config3D(n=32, length=16, scattering_nm=0))
    s.psi = np.roll(s.psi, 14, axis=0)
    s.release()
    s.advance(20)
    assert s.warning and s.steps == 1
    frozen = s.psi.copy()
    s.advance(20)
    assert np.array_equal(s.psi, frozen)
    for kwargs in (
        {"n": True},
        {"length": 48, "n": 32},
        {"dt": float("nan")},
        {"atoms": 2},
        {"fz_hz": 5},
        {"scattering_nm": -1},
    ):
        with pytest.raises(ValueError):
            Config3D(**kwargs)
