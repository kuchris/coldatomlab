import json
import math

import numpy as np
import pytest

from coldatomlab.solver import Config, Solver, replay


def evolve(sim, steps):
    while steps:
        count = min(100, steps)
        sim.advance(count)
        assert not sim.warning, sim.warning
        steps -= count


def test_harmonic_ground_state_and_stationarity():
    s = Solver(Config(interaction=0))
    exact = s.gaussian()
    exact /= np.sqrt(np.sum(exact**2) * s.dx**2)
    assert np.linalg.norm(np.abs(s.psi) - exact) * s.dx < 2e-6
    d = s.diagnostics()
    assert abs(d["energy"] - 1.2) < 1e-8
    assert abs(d["width_x"] - 1 / math.sqrt(2)) < 2e-6
    rho = np.abs(s.psi) ** 2
    evolve(s, 200)
    assert np.max(np.abs(np.abs(s.psi) ** 2 - rho)) < 1e-5


def test_free_gaussian_expansion():
    s = Solver(Config(interaction=0, dt=0.01))
    s.release()
    evolve(s, 200)
    d = s.diagnostics()
    for axis, omega in (("x", 1), ("y", 1.4)):
        exact = math.sqrt((1 + (omega * s.time) ** 2) / (2 * omega))
        assert abs(d[f"width_{axis}"] / exact - 1) < 1e-5
    assert abs(d["norm"] - 1) < 1e-11


def test_interference_phase_changes_center():
    results = []
    for phase in (0, math.pi):
        s = Solver(Config(experiment="double", interaction=0, phase=phase, dt=0.01))
        evolve(s, 200)
        results.append(abs(s.psi[s.config.n // 2, s.config.n // 2]) ** 2)
    assert results[0] > 0.002
    assert results[1] < results[0] * 1e-12


def test_interacting_energy_converges_in_static_trap():
    # A displaced interacting state excites motion; a stationary state would be too easy.
    initial = Solver(Config(n=64, length=24, interaction=20))
    errors = []
    for dt in (0.02, 0.01, 0.005):
        s = Solver(Config(experiment="double", n=64, length=24, interaction=20, dt=dt))
        s.psi = np.roll(initial.psi, 3, axis=1)
        s.release_step = None
        s.potential = s.trap.copy()
        e0 = s.diagnostics()["energy"]
        evolve(s, round(1 / dt))
        d = s.diagnostics()
        errors.append(abs(d["energy"] - e0))
        assert abs(d["norm"] - 1) < 2e-11
    assert errors[1] < errors[0] * 0.35
    assert errors[2] < errors[1] * 0.35


def test_time_grid_domain_convergence():
    results = []
    # Same physical initial state; separate dt, dx and domain-size refinements.
    for n, length, dt in ((128, 32, 0.01), (128, 32, 0.005), (256, 32, 0.005), (256, 64, 0.005)):
        s = Solver(Config(experiment="double", n=n, length=length, dt=dt, interaction=20))
        evolve(s, round(1 / dt))
        results.append(s)
    base, half_dt, fine_grid, large_domain = results
    for refined in (half_dt, fine_grid, large_domain):
        assert abs(base.diagnostics()["width_x"] / refined.diagnostics()["width_x"] - 1) < 0.005
    # Compare exact coincident coordinates: no interpolation error in the convergence signal.
    profiles = [np.abs(s.psi[s.config.n // 2]) ** 2 for s in results]
    for actual, reference in (
        (profiles[0], profiles[1]),
        (profiles[1], profiles[2][::2]),
        (profiles[1], profiles[3][64:192]),
    ):
        assert np.linalg.norm(actual - reference) / np.linalg.norm(reference) < 0.01


def test_interacting_prepared_state_remains_stationary():
    s = Solver(Config(interaction=20))
    width = s.diagnostics()["width_x"]
    evolve(s, 200)
    assert abs(s.diagnostics()["width_x"] / width - 1) < 0.002


def test_export_replays_delayed_release_and_reset():
    s = Solver(Config(interaction=0))
    initial = s.psi.copy()
    evolve(s, 17)
    s.release()
    evolve(s, 41)
    data = json.loads(json.dumps(s.export()))
    restored = replay(data)
    assert restored.steps == 58 and restored.release_step == 17
    np.testing.assert_allclose(restored.psi, s.psi, atol=1e-13)
    s.reset()
    assert s.time == 0 and not s.released
    np.testing.assert_array_equal(s.psi, initial)


def test_boundary_guard_and_mask():
    s = Solver(Config(experiment="double", interaction=0, n=64, length=24, dt=0.02))
    while not s.warning:
        s.advance(100)
    assert s.edge_mass() > 0.001
    assert s.time < 20
    previous = s.steps
    s.advance(10)
    assert s.steps == previous
    phase = s.snapshot()["phase"]
    assert any(value is None for row in phase for value in row)
    s.reset()
    assert not s.warning


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dt": 0},
        {"phase": float("nan")},
        {"n": 100},
        {"n": True},
        {"interaction": -1},
        {"omega_x": "1"},
        {"n": 64, "length": 64},
        {"experiment": "invalid"},
    ],
)
def test_invalid_configuration(kwargs):
    with pytest.raises(ValueError):
        Config(**kwargs)
