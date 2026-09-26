"""Analytic limits and conservation for the published reduced-model equations."""

import math

import numpy as np
import pytest
from scipy.special import lambertw

from coldatomlab.vortex_paper import PaperVortex


def test_free_oscillator_expansion_and_core_definition():
    s = PaperVortex(0, cells=512)
    expected = math.sqrt(-lambertw(-math.exp(-2)).real / 2)
    for step in range(5):
        d = s.diagnostics()
        t = d["time"]
        assert d["norm"] == pytest.approx(1, abs=1e-11)
        assert d["radial_rms"] == pytest.approx(math.sqrt(2 * (1 + t * t)), rel=0.001)
        assert d["axial_rms"] == pytest.approx(math.sqrt((1 + t * t) / 2), rel=2e-6)
        assert d["core_ratio"] == pytest.approx(expected, abs=0.001)
        s.advance(250)


def test_interacting_norm_energy_and_reference_refinement():
    ratios = []
    for cells in [256, 512, 1024]:
        s = PaperVortex(20, cells=cells)
        start = s.diagnostics()
        assert s.preparation["radial_residual"] < 1e-5
        s.advance(1000)
        end = s.diagnostics()
        assert end["norm"] == pytest.approx(1, abs=1e-10)
        assert end["energy"] == pytest.approx(start["energy"], abs=3e-6)
        assert end["core_ratio"] > start["core_ratio"]
        assert end["edge_probability"] < 1e-10
        ratios.append(end["core_ratio"])
    assert abs(ratios[-1] - ratios[-2]) < 0.0005
    assert np.isfinite(ratios).all()
