from dataclasses import asdict, replace

import numpy as np
import pytest

from coldatomlab.physical import HBAR, H, Physical
from coldatomlab.replay import verify_export
from coldatomlab.solver import Config, Solver


def test_si_conversion_and_gaussian_reduction():
    p = Physical()
    u = p.scales()
    assert u["length_um"] == pytest.approx(2.41143618, rel=1e-8)
    assert u["time_ms"] == pytest.approx(7.95774715, rel=1e-8)
    assert u["interaction"] == pytest.approx(22.03687574, rel=1e-8)
    # Independently integrate the axial normalized density squared.
    az = u["axial_length_um"] * 1e-6
    z = np.linspace(-8 * az, 8 * az, 20001)
    density = np.exp(-((z / az) ** 2)) / (np.sqrt(np.pi) * az)
    g3d = 4 * np.pi * HBAR**2 * p.scattering_nm * 1e-9 / u["mass_kg"]
    g2d = g3d * np.trapezoid(density**2, z)
    derived = p.atoms * g2d / (H * p.reference_hz * (u["length_um"] * 1e-6) ** 2)
    assert derived == pytest.approx(u["interaction"], rel=1e-12)
    assert replace(p, reference_hz=80).scales()["interaction"] == u["interaction"]
    assert replace(p, atoms=400).scales()["interaction"] == pytest.approx(2 * u["interaction"])
    assert replace(p, axial_hz=8000).scales()["interaction"] == pytest.approx(2 * u["interaction"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"atoms": True},
        {"atoms": 20.5},
        {"reference_hz": 0},
        {"axial_hz": float("nan")},
        {"scattering_nm": -1},
        {"species": "fermion"},
        {"mass_u": float("inf")},
    ],
)
def test_invalid_physical_inputs(kwargs):
    with pytest.raises(ValueError):
        Physical(**kwargs)


def test_derived_g_is_authoritative_and_limited():
    c = Config(physical=asdict(Physical()), interaction=99)
    assert c.interaction == Physical().scales()["interaction"]
    with pytest.raises(ValueError, match="Derived g"):
        Config(physical=Physical(atoms=100000))
    custom = Physical(species="custom", mass_u=23)
    assert custom.scales()["length_um"] > Physical().scales()["length_um"]


def test_physical_free_expansion_against_si_analytic_width():
    p = Physical(scattering_nm=0)
    s = Solver(Config(physical=p, dt=0.01))
    s.release()
    s.advance(100)
    u = p.scales()
    t = s.time * u["time_ms"] * 1e-3
    omega = 2 * np.pi * p.reference_hz
    expected = np.sqrt(HBAR / (2 * u["mass_kg"] * omega) * (1 + (omega * t) ** 2)) * 1e6
    assert s.history[-1]["width_x"] * u["length_um"] == pytest.approx(expected, rel=2e-5)
    n2d = abs(s.psi) ** 2 * p.atoms / u["length_um"] ** 2
    assert n2d.sum() * (s.dx * u["length_um"]) ** 2 == pytest.approx(p.atoms, abs=1e-8)
    assert s.physical_report()["status"] == "supported"
    assert verify_export(s.export())["max_wavefunction_error"] < 1e-12


def test_regime_detects_weak_confinement_and_records_actual_density():
    s = Solver(Config(physical=Physical(axial_hz=20)))
    report = s.physical_report()
    assert report["status"] == "outside"
    assert report["ratios"]["trap_over_axial"] == pytest.approx(1.4)
    assert report["ratios"]["initial_mu_over_gap"] > 1
    s = Solver(Config(physical=Physical(axial_hz=200)))
    assert s.physical_report()["status"] == "marginal"
    assert s.physical_report()["ratios"]["peak_interaction_over_gap"] == pytest.approx(
        s.config.interaction * abs(s.psi).max() ** 2 / 10
    )


def test_guided_runs_complete_with_expected_bias_and_hold_response():
    results = []
    for bias, hold in [(0, 1), (0.5, 1), (-0.5, 1), (0.5, 2)]:
        s = Solver(
            Config(
                experiment="sequence",
                physical=Physical(),
                dt=0.01,
                bias=bias,
                hold_time=hold,
                expansion_time=2,
            )
        )
        worst = 0.0
        while s.steps < s.protocol.release_at:
            s.advance(min(100, s.protocol.release_at - s.steps))
            worst = max(worst, s.physical_report()["ratios"]["peak_interaction_over_gap"])
        phase = s.history[-1]["relative_phase"]
        while not s.complete and not s.warning:
            s.advance(100)
        assert s.complete and not s.warning
        assert abs(s.history[-1]["norm"] - 1) < 1e-10
        assert s.physical_report()["status"] == "supported" and worst < 0.1
        results.append((phase, s.history[-1]["left_fraction"]))
    assert abs(results[0][0]) < 1e-8
    assert results[1][0] == pytest.approx(-results[2][0], abs=1e-8)
    assert results[1][1] + results[2][1] == pytest.approx(1, abs=1e-5)
    assert results[1][0] < -0.4
    assert results[3][0] < results[1][0] - 0.35


def test_export_restores_physical_parameters_and_old_exports():
    s = Solver(Config(experiment="double", physical=Physical(), n=64))
    s.advance(4)
    data = s.export()
    assert data["physical"]["parameters"]["reference_hz"] == 20
    assert verify_export(data)["max_wavefunction_error"] < 1e-12
    old = Solver(Config(experiment="double", n=64)).export()
    del old["config"]["physical"]
    del old["physical"]
    assert verify_export(old)["max_wavefunction_error"] < 1e-12


def test_physical_demo_refines_step_grid_and_domain():
    results = []
    for dt, n, length in ((0.01, 128, 32), (0.005, 128, 32), (0.005, 256, 32), (0.005, 256, 64)):
        sim = Solver(
            Config(
                experiment="sequence",
                physical=Physical(),
                dt=dt,
                n=n,
                length=length,
                hold_time=1,
                expansion_time=2,
            )
        )
        while not sim.complete and not sim.warning:
            sim.advance(100)
        assert sim.complete and not sim.warning
        results.append(abs(sim.psi) ** 2)
    baseline, fine, grid, domain = results
    errors = [np.linalg.norm(baseline - fine) / np.linalg.norm(fine)]
    for other in (grid[::2, ::2], domain[64:192, 64:192]):
        errors.append(np.linalg.norm(fine - other) / np.linalg.norm(other))
    print("Physical demo relative density errors (step, grid, domain):", errors)
    assert max(errors) < 0.01
