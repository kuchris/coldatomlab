from dataclasses import replace

import numpy as np
import pytest

from coldatomlab.protocol import fringe_metrics
from coldatomlab.replay import verify_export
from coldatomlab.solver import Config, Solver, replay


def until(sim, step):
    while sim.steps < step:
        sim.advance(min(100, step - sim.steps))
        assert not sim.warning, sim.warning


def test_protocol_applies_a_real_barrier_and_stops_exactly():
    s = Solver(Config(experiment="sequence", interaction=0, dt=0.01, bias=0, hold_time=0.5))
    initial = s.psi.copy()
    p = s.protocol
    np.testing.assert_array_equal(p.potential(0), s.trap)
    assert p.settings(p.split_end / 2) == (6, 0)
    until(s, p.split_end)
    rho = abs(s.psi) ** 2
    assert rho[64, 64] / rho.max() < 0.01
    assert not np.allclose(initial, s.psi)
    assert s.diagnostics()["left_fraction"] == pytest.approx(0.5, abs=1e-10)
    until(s, p.release_at)
    assert s.release_step == p.release_at
    np.testing.assert_array_equal(s.potential, np.zeros_like(s.trap))
    until(s, p.end)
    assert s.complete and s.steps == p.end
    s.advance(100)
    assert s.steps == p.end
    assert abs(s.diagnostics()["norm"] - 1) < 1e-10
    saved = s.psi.copy()
    restored = replay(s.export())
    np.testing.assert_allclose(restored.psi, saved, atol=1e-12)
    s.reset()
    np.testing.assert_array_equal(s.psi, initial)
    assert s.steps == 0 and s.release_step is None and not s.complete


def test_slow_split_leaves_less_energy_at_identical_final_potential():
    energies = []
    for duration in (0.2, 4):
        s = Solver(
            Config(experiment="sequence", interaction=0, dt=0.01, split_time=duration, bias=0)
        )
        until(s, s.protocol.split_end)
        energies.append(s.diagnostics()["energy"])
    assert energies[1] < energies[0] - 1


def test_hold_bias_accumulates_phase_with_expected_sign_and_scale():
    phases = []
    fractions = []
    for bias in (-0.5, 0, 0.5):
        s = Solver(Config(experiment="sequence", interaction=0, dt=0.01, hold_time=1, bias=bias))
        until(s, s.protocol.release_at)
        d = s.diagnostics()
        # Well-separated arms approach delta(phi)=-delta(V)*T. The smooth bias
        # approaches its asymptote over the occupied wavepacket, so allow 0.03 rad.
        assert abs(d["relative_phase"] + bias) < 0.03
        phases.append(d["relative_phase"])
        fractions.append(d["left_fraction"])
    assert phases[0] == pytest.approx(-phases[2], abs=1e-10)
    assert phases[1] == pytest.approx(0, abs=1e-10)
    assert fractions[0] + fractions[2] == pytest.approx(1, abs=1e-10)


def test_time_dependent_evolution_converges_under_step_grid_and_domain_refinement():
    c = Config(
        experiment="sequence",
        interaction=20,
        split_time=1,
        hold_time=0.5,
        expansion_time=0.5,
        dt=0.02,
    )
    sims = []
    for dt, n, length in (
        (0.02, 128, 32),
        (0.01, 128, 32),
        (0.005, 128, 32),
        (0.005, 256, 32),
        (0.005, 256, 64),
    ):
        s = Solver(replace(c, dt=dt, n=n, length=length))
        until(s, s.protocol.end)
        sims.append(s)
    coarse, medium, fine, grid, domain = sims

    def rho(s):
        return abs(s.psi) ** 2

    err1 = np.linalg.norm(rho(coarse) - rho(fine))
    err2 = np.linalg.norm(rho(medium) - rho(fine))
    assert err2 < 0.35 * err1
    for comparison in (rho(grid)[::2, ::2], rho(domain)[64:192, 64:192]):
        assert np.linalg.norm(rho(fine) - comparison) / np.linalg.norm(comparison) < 0.01


def test_fringe_estimator_recovers_known_modulation_and_rejects_unresolved_cases():
    x = np.arange(-16, 16, 0.125)
    profile = 1 + 0.6 * np.cos(2 * np.pi * x / 2)
    result = fringe_metrics(x, profile)
    assert result["fringe_spacing"] == pytest.approx(2)
    assert result["fringe_contrast"] == pytest.approx(0.6)
    assert fringe_metrics(x, np.exp(-x * x))["fringe_spacing"] is None
    assert fringe_metrics(x, np.zeros_like(x))["fringe_contrast"] is None
    assert fringe_metrics(x, 1 + 0.01 * np.cos(2 * np.pi * x / 2))["fringe_spacing"] is None


def test_step_quantization_partial_replay_and_comparison_export():
    c = Config(
        experiment="sequence",
        interaction=0,
        dt=0.007,
        split_time=0.1,
        hold_time=0,
        expansion_time=0.1,
    )
    s = Solver(c)
    assert s.protocol.split_end == 14 and s.protocol.release_at == 14
    until(s, 5)
    a = s.export()
    assert a["release_step"] is None
    until(s, s.protocol.end)
    b = s.export()
    report = verify_export({"schema": "coldatomlab-comparison-v1", "reference": a, "current": b})
    assert report["reference"]["max_wavefunction_error"] < 1e-12
    assert report["current"]["max_wavefunction_error"] < 1e-12
    with pytest.raises(ValueError, match="automatically"):
        s.release()
    with pytest.raises(ValueError, match="disagrees"):
        replay({**b, "release_step": 0})


@pytest.mark.parametrize(
    "kwargs",
    [
        {"barrier_width": 0.1},
        {"bias": float("inf")},
        {"split_time": 8, "hold_time": 6, "expansion_time": 8},
        {"n": 64, "length": 32, "barrier_width": 0.7},
    ],
)
def test_invalid_sequences(kwargs):
    with pytest.raises(ValueError):
        Config(experiment="sequence", **kwargs)
