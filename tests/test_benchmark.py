import numpy as np
import pytest

from coldatomlab.benchmark import fringe_fit, propagate, report


def test_free_propagation_matches_independent_gaussian_and_is_unitary():
    x, psi, analytic = propagate()
    dx = x[1] - x[0]
    assert abs(np.sum(abs(psi) ** 2) * dx - 1) < 1e-12
    assert np.linalg.norm(psi - analytic) * np.sqrt(dx) < 1e-7
    _, twice, _ = propagate(parts=2)
    assert np.max(abs(psi - twice)) < 1e-12


@pytest.mark.parametrize("period,phase,center", [(31.7, 0.8, 5), (52.3, -1.1, -8)])
def test_fit_recovers_unknown_period_from_profile(period, phase, center):
    x = np.linspace(-200, 200, 1801)
    density = (
        0.014
        * np.exp(-0.5 * ((x - center) / 72) ** 2)
        * (1 + 0.72 * np.cos(2 * np.pi * x / period + phase))
    )
    fit, reconstructed = fringe_fit(x, density)
    assert abs(fit["period_um"] - period) < 1e-6
    assert abs(fit["contrast"] - 0.72) < 1e-6
    assert abs(fit["center_um"] - center) < 1e-6
    assert np.max(abs(reconstructed - density)) < 1e-8


def test_unresolved_profile_is_rejected():
    x = np.linspace(-200, 200, 1024)
    with pytest.raises(ValueError, match="three resolved"):
        fringe_fit(x, np.exp(-0.5 * (x / 50) ** 2))


def test_benchmark_converges_without_claiming_experimental_agreement():
    data = report()
    base = data["base"]
    assert abs(base["fit"]["period_um"] - base["finite_gaussian_period_um"]) < 1e-4
    for name in ("finer_grid", "larger_domain", "two_half_steps"):
        assert abs(data["checks"][name]["period_change_um"]) < 1e-5
    for case in [base, *data["checks"].values()]:
        assert abs(case["norm"] - 1) < 1e-12
        assert case["analytic_wavefunction_l2_error"] < 1e-7
        assert case["edge_probability"] < 1e-10
    # Published figures remain distinct from recalculation with rounded inputs.
    assert data["published"]["measured_period_um"] == 41.5
    assert data["published"]["quoted_theory_um"] == 39.8
    assert data["published"]["measurement_uncertainty_um"] is None
    assert abs(base["point_source_period_um"] - 40.0544) < 1e-4
    assert data["published"]["raw_data_available_in_reference"] is False
    assert len(data["limitations"]) >= 1
