from dataclasses import replace

import numpy as np
import pytest

from coldatomlab.interferometry3d import (
    drive,
    fringe_measurement,
    gaussian_pair,
    measurements,
    stages,
)
from coldatomlab.solver3d import Config3D, Solver3D, replay3d


def finish(s):
    while not s.complete and not s.warning:
        s.advance(20)
    assert not s.warning


@pytest.mark.parametrize("phase", [0, np.pi, 0.7])
def test_pair_exact_complex_field(phase):
    c = Config3D(
        n=48,
        length=24,
        dt=0.01,
        scattering_nm=0,
        experiment="pair",
        relative_phase=phase,
        duration=1,
    )
    s = Solver3D(c)
    finish(s)
    exact = gaussian_pair(c, s.x, s.time)
    assert np.linalg.norm((s.psi - exact).ravel()) * s.dx**1.5 < 2e-6
    assert abs(s.diagnostics()["norm"] - 1) < 1e-12
    if phase == np.pi:
        assert max(abs(s.psi[c.n // 2]).ravel()) < 1e-12
    assert np.max(abs(replay3d(s.export()).psi - s.psi)) < 1e-12
    s.reset()
    assert s.release_step == 0 and s.steps == 0


def test_sequence_stages_bias_and_replay():
    c = Config3D(
        n=32,
        length=16,
        dt=0.01,
        atoms=100,
        scattering_nm=0,
        experiment="sequence",
        barrier_width=1,
        split_time=0.205,
        hold_time=0.105,
        duration=0.1,
    )
    assert stages(c) == (21, 32, 42)
    assert drive(c, 0) == (0, 0)
    assert drive(c, 21) == (12, 1)
    assert drive(c, 32) == (0, 0)
    s = Solver3D(c)
    with pytest.raises(ValueError, match="automatic"):
        s.release()
    s.advance(20)
    assert np.max(abs(replay3d(s.export()).psi - s.psi)) < 1e-12
    finish(s)
    assert s.steps == 42 and s.release_step == 32
    assert np.max(abs(replay3d(s.export()).psi - s.psi)) < 1e-12
    assert s.snapshot()["interferometry"]["stage"] == "Complete"
    assert np.all(np.array(s.snapshot()["interferometry"]["potential"]) == 0)
    bad = s.export()
    bad["release_step"] = 31
    with pytest.raises(ValueError, match="automatic"):
        replay3d(bad)
    s.reset()
    assert s.release_step is None and s.steps == 0


def test_mirror_phase_sign_and_unresolved_fringe():
    c = Config3D(n=48, length=24, scattering_nm=0, experiment="pair", relative_phase=0.7)
    s = Solver3D(c)
    m = measurements(c, s.x, s.psi, 0, True)
    assert m["mirror_phase"] == pytest.approx(0.7, abs=2e-4)
    assert m["left_fraction"] == pytest.approx(0.5, abs=1e-10)
    assert m["fringes"]["spacing"] is None


def test_interferometer_validation():
    with pytest.raises(ValueError, match="zero scattering"):
        Config3D(experiment="pair")
    with pytest.raises(ValueError, match="two grid"):
        Config3D(experiment="sequence", n=32, length=16)
    with pytest.raises(ValueError, match="Unknown"):
        Config3D(experiment="invalid")
    with pytest.raises(ValueError, match="relative_phase"):
        replace(Config3D(), relative_phase=float("nan"))


def test_fringe_resolution_and_phase_mask():
    x = np.linspace(-10, 10, 401)
    m = fringe_measurement(x, 1 + 0.8 * np.cos(2 * np.pi * x / 4))
    assert m["spacing"] == pytest.approx(4, abs=1e-10)
    assert m["contrast"] == pytest.approx(0.8, abs=1e-10)
    sparse_x = np.arange(-10, 11, 2.0)
    assert (
        fringe_measurement(sparse_x, 1 + 0.8 * np.cos(2 * np.pi * sparse_x / 4))["spacing"] is None
    )
    c = Config3D(n=32, length=16, experiment="pair", scattering_nm=0)
    s = Solver3D(c)
    s.psi[:16] = 0
    assert measurements(c, s.x, s.psi, 0, True)["mirror_phase"] is None


def test_zero_hold_releases_at_end_of_split():
    c = Config3D(
        n=32,
        length=16,
        experiment="sequence",
        scattering_nm=0,
        barrier_width=1,
        split_time=0.1,
        hold_time=0,
        duration=0.1,
        dt=0.01,
    )
    s = Solver3D(c)
    s.advance(10)
    assert s.release_step == 10
    assert s.snapshot()["interferometry"]["stage"] == "Expansion"
    finish(s)
    assert s.steps == 20
