"""Independent physical invariants, model limits and export integrity."""

import copy

import numpy as np
import pytest

from coldatomlab.vortex import Vortex, drive, scales, validate, verify_export, winding_diagnostics


@pytest.mark.parametrize("charge", [-1, 0, 1])
def test_oscillator_vortex(charge):
    sim = Vortex(dict(n=32, width=1, charge=charge))
    initial = sim.psi.copy()
    d = sim.diagnostics()
    assert d["winding"] == charge
    assert d["lz"] == pytest.approx(charge, abs=2e-7)
    assert d["energy"] == pytest.approx(2 + abs(charge), abs=2e-6)
    assert d["positive"] - d["negative"] == charge
    assert d["flow_circulation_quanta"] == pytest.approx(charge, abs=0.009)
    sim.advance(250)
    after = sim.diagnostics()
    expected = initial * np.exp(-1j * (2 + abs(charge)))
    assert np.linalg.norm(sim.psi - expected) * sim.dx**1.5 < 3e-5
    assert after["norm"] == pytest.approx(1, abs=2e-12)
    assert after["energy"] == pytest.approx(d["energy"], abs=1e-8)
    assert after["lz"] == pytest.approx(charge, abs=2e-7)


def test_density_hole_does_not_imply_winding():
    sim = Vortex(dict(n=32, width=1))
    hollow = abs(sim.psi).astype(complex)
    d = winding_diagnostics(hollow, sim.config)
    assert d["loop_reliable"] and d["winding"] == 0 and not d["crossings"]
    empty = winding_diagnostics(np.zeros_like(hollow), sim.config)
    assert empty["winding"] is None and not empty["loop_reliable"]


def test_grid_improves_flow_integral():
    errors = []
    for n in [32, 64]:
        sim = Vortex(dict(n=n, width=1))
        errors.append(abs(sim.diagnostics()["flow_circulation_quanta"] - 1))
    assert errors[1] < errors[0] / 4


def test_second_order_time_refinement():
    errors = []
    for dt in [0.008, 0.004, 0.002]:
        sim = Vortex(dict(n=64, width=1, dt=dt))
        initial = sim.psi.copy()
        sim.advance(round(0.8 / dt))
        errors.append(np.linalg.norm(sim.psi - initial * np.exp(-2.4j)) * sim.dx**1.5)
    assert 3.8 < errors[0] / errors[1] < 4.2
    assert 3.5 < errors[1] / errors[2] < 4.5


def test_smooth_drive_and_units():
    c = validate(dict(height=12, stir_time=4))
    assert drive(c, 0)[0] == 0 and drive(c, 4)[0] == 0 and drive(c, 5)[0] == 0
    assert drive(c, 1)[0] == 12
    assert drive(c, 1e-5)[0] < 1e-8 and drive(c, 4 - 1e-5)[0] < 1e-8
    assert scales()["length_um"] == pytest.approx(1.525, abs=0.001)
    assert scales()["circulation_um2_ms"] == pytest.approx(4.591, abs=0.001)


@pytest.mark.parametrize(
    "config",
    [
        dict(n=48),
        dict(n=True),
        dict(g=float("nan")),
        dict(dt=0),
        dict(charge=2),
        dict(unknown=1),
        dict(width=0.5, n=32),
        dict(length=32, n=32),
        dict(ramp=3, stir_time=4),
    ],
)
def test_invalid_config(config):
    with pytest.raises(ValueError):
        validate(config)


def export_reference():
    sim = Vortex(dict(n=32, width=1, duration=0.1))
    rows = [sim.diagnostics()]
    sim.advance(25)
    rows.append(sim.diagnostics())

    def packed(p):
        return np.stack([p.real, p.imag], axis=-1).ravel().tolist()

    return dict(
        schema="coldatomlab-vortex-v1",
        version="0.16.0",
        array_order="x,y,z interleaved real,imag",
        config=sim.config,
        scales=scales(),
        steps=25,
        initial=packed(sim.initial),
        field=packed(sim.psi),
        history=rows,
    )


def test_independent_export_replay():
    result = verify_export(export_reference())
    assert result["verified"] and result["evolution_l2_error"] < 1e-12


@pytest.mark.parametrize(
    "kind", ["initial", "field", "time", "norm", "winding", "flow", "scales", "order", "steps"]
)
def test_export_tampering(kind):
    data = export_reference()
    if kind in ["initial", "field"]:
        data[kind][10000] += 0.2
    elif kind == "time":
        data["history"][-1]["time"] += 0.1
    elif kind == "norm":
        data["history"][-1]["norm"] += 0.01
    elif kind == "winding":
        data["history"][-1]["winding"] = 0
    elif kind == "flow":
        data["history"][-1]["flow_circulation_quanta"] = 0
    elif kind == "scales":
        data["scales"]["time_ms"] *= 2
    elif kind == "order":
        data["array_order"] = "z,y,x"
    elif kind == "steps":
        data["steps"] = 26
    with pytest.raises(ValueError):
        verify_export(copy.deepcopy(data))
