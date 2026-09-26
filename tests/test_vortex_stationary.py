"""Physical scales and independently prepared stationary interacting vortices."""

import numpy as np
import pytest

from coldatomlab.vortex import Vortex, parent_config, scales, validate
from coldatomlab.vortex_stationary import project, residual


@pytest.mark.parametrize("charge", [-1, 1])
def test_stationary_interacting_charge_and_hold(charge):
    s = Vortex(dict(n=32, width=1, stationary=1, charge=charge, g=4 * np.pi * 20, axial_hz=50))
    p = s.preparation
    assert p["relative_stationary_residual"] < 1e-5
    assert 5.5 < p["chemical_potential"] < 5.6
    initial = s.psi.copy()
    before = s.diagnostics()
    s.advance(100)
    after = s.diagnostics()
    assert after["winding"] == charge
    assert after["norm"] == pytest.approx(1, abs=1e-11)
    assert after["lz"] == pytest.approx(charge, abs=3e-5)
    assert after["energy"] == pytest.approx(before["energy"], abs=1e-8)
    assert np.linalg.norm(abs(initial) ** 2 - abs(s.psi) ** 2) * s.dx**1.5 < 1e-5
    assert (
        np.linalg.norm(s.psi - initial * np.exp(-1j * p["chemical_potential"] * 0.4)) * s.dx**1.5
        < 1e-4
    )


def test_projection_idempotent_and_preserves_analytic_charge():
    s = Vortex(dict(n=32, width=1, g=0, stationary=1))
    assert project(s.psi, 1) == pytest.approx(s.psi, abs=1e-12)
    assert np.linalg.norm(project(s.psi, -1)) < 1e-12
    mu, error = residual(s, s.psi)
    assert mu == pytest.approx(3, abs=1e-6)
    assert error < 1e-4


def test_physical_trap_scales():
    c = validate(dict(radial_hz=100, axial_hz=150, g=100))
    assert scales(c)["length_um"] == pytest.approx(scales()["length_um"] / np.sqrt(2))
    assert scales(c)["time_ms"] == pytest.approx(scales()["time_ms"] / 2)
    pc = parent_config(c)
    assert pc.fx_hz == pc.fy_hz == 100 and pc.fz_hz == 150
