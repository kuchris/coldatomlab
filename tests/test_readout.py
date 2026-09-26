import copy
import json
import math
import subprocess

import numpy as np
import pytest
from scipy.linalg import expm
from scipy.stats import binom

from coldatomlab import readout
from coldatomlab.replay import verify_export
from coldatomlab.twomode import hamiltonian, validate


def plan(**changes):
    return (
        dict(
            base=validate(dict(atoms=8, left_fraction=0.5, phase=0.7, tunnelling_hz=0)),
            hold_ms=0,
            echo=False,
            pulse_j_hz=10,
            duration_error=0,
            points=12,
            shots=256,
            seed=17,
        )
        | changes
    )


def js(code, data):
    proc = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "require('./coldatomlab/web/preparation.js');require('./coldatomlab/web/echo.js');require('./coldatomlab/web/readout.js');"
            "const data=JSON.parse(require('fs').readFileSync(0,'utf8'));" + code,
        ],
        input=json.dumps(data),
        capture_output=True,
        text=True,
        encoding="utf8",
        check=True,
    )
    return json.loads(proc.stdout)


def report(p, count=None):
    return js(
        "const p=Readout.validate(data.p),s=Readout.incoming(p);"
        "const n=data.count??p.points,rs=Array.from({length:n},(_,i)=>Readout.point(p,s,i));"
        "console.log(JSON.stringify(Readout.report(p,s,rs,n===p.points?'complete':'cancelled')));",
        dict(p=p, count=count),
    )


def field(s):
    return np.array(s["real"]) + 1j * np.array(s["imag"])


@pytest.mark.parametrize("phase", [-math.pi, -1.2, 0, math.pi / 2, math.pi])
def test_binomial_readout_sign_and_both_quadratures(phase):
    p = plan()
    p["base"]["phase"] = phase
    d = report(p)
    n = p["base"]["atoms"]
    for row in d["records"]:
        left = (1 + math.cos(phase - row["alpha"])) / 2
        for arm in ("ideal", "finite"):
            state = row["arms"][arm]["state"]
            assert state["probability"] == pytest.approx(
                binom.pmf(np.arange(n + 1), n, left), abs=1e-12
            )
        assert row["arms"]["direct"]["state"]["mean_left"] == pytest.approx(n / 2)
    inferred = d["fits"]["ideal"]["model"]["phase"]
    assert abs(np.angle(np.exp(1j * (inferred - phase)))) < 1e-12


@pytest.mark.parametrize(
    "config,extra",
    [
        ({}, {}),
        (dict(initial="fock"), {}),
        (dict(initial="gaussian", sigma=0.5, phase=-2.7), {}),
        (dict(interaction_hz=0.3, bias_hz=8), dict(hold_ms=150, echo=True, duration_error=0.2)),
        (dict(atoms=3, left_fraction=0.8, bias_hz=-12), dict(hold_ms=317, pulse_j_hz=0.5)),
        (dict(atoms=100, interaction_hz=2, bias_hz=20), dict(points=8, shots=16, hold_ms=1000)),
    ],
)
def test_independent_full_state_and_count_replay(config, extra):
    p = plan(**extra)
    p["base"].update(config)
    result = verify_export(report(p))
    assert result["maximum_complex_state_l2"] < 5e-8
    assert result["maximum_norm_drift"] < 1e-9


def test_finite_pulse_uses_actual_hamiltonian_not_ideal_swap():
    p = plan(duration_error=0.3, hold_ms=220, echo=True)
    p["base"].update(interaction_hz=0.7, bias_hz=-5, initial="gaussian")
    d = report(p)
    n = p["base"]["atoms"]
    c = p["base"] | dict(tunnelling_hz=p["pulse_j_hz"])
    prop = expm(-2j * np.pi * hamiltonian(c) * readout.width(p) / 1000)
    for row in d["records"]:
        incoming = field(d["source"]) * np.exp(
            -1j * (n - np.arange(n + 1)) * (row["alpha"] + np.pi / 2)
        )
        out = row["arms"]["finite"]["state"]
        assert field(out) == pytest.approx(prop @ incoming, abs=1e-11)
        assert out["time_ms"] == pytest.approx(p["hold_ms"] + readout.width(p))
    assert d["fits"]["finite"]["model"]["residual_rms"] > 1e-4


def test_echo_conjugates_phase_cancels_static_bias():
    p = plan(echo=True, hold_ms=375)
    p["base"].update(bias_hz=11)
    d = report(p)
    assert d["source"]["phase"] == pytest.approx(-0.7)
    assert d["fits"]["ideal"]["model"]["phase"] == pytest.approx(-0.7)


def test_free_bias_phase_sign_and_interaction_collapse():
    p = plan(hold_ms=25)
    p["base"].update(bias_hz=3)
    d = report(p)
    assert d["source"]["phase"] == pytest.approx(0.7 - 2 * np.pi * 3 * 0.025)
    p["base"].update(interaction_hz=1, bias_hz=0)
    p["hold_ms"] = 250
    d = report(p)
    assert d["source"]["phase"] is None
    assert d["fits"]["ideal"]["model"]["phase"] is None


def test_no_coherence_masks_inferred_phase():
    p = plan()
    p["base"].update(initial="fock")
    d = report(p)
    assert d["source"]["phase"] is None
    assert d["fits"]["ideal"]["measured"]["phase"] is None
    assert d["fits"]["ideal"]["measured"]["phase_se"] is None
    assert d["fits"]["ideal"]["model"]["phase"] is None


def test_fit_uses_counts_and_not_model_truth():
    rows = [
        dict(
            alpha=2 * np.pi * k / 12,
            z=0.1 + 0.6 * np.cos(2 * np.pi * k / 12 - 1.1),
            variance_z_mean=0.001,
        )
        for k in range(12)
    ]
    fit = js("console.log(JSON.stringify(Readout.fit(data)));", rows)
    assert fit["offset"] == pytest.approx(0.1)
    assert fit["contrast"] == pytest.approx(0.6)
    assert fit["phase"] == pytest.approx(1.1)
    assert fit["phase_se"] == pytest.approx(math.sqrt(2 * 0.001 / 12) / 0.6)
    for r in rows:
        r["variance_z_mean"] *= 4
    larger = js("console.log(JSON.stringify(Readout.fit(data)));", rows)
    assert larger["phase_se"] == pytest.approx(2 * fit["phase_se"])
    assert larger["phase"] == fit["phase"]


def test_seeded_counts_disjoint_blocks_and_statistical_precision():
    p = plan(shots=1024)
    d = report(p)
    assert report(p) == d
    changed = report(p | dict(seed=18))
    assert (
        changed["records"][0]["arms"]["ideal"]["measurement"]
        != d["records"][0]["arms"]["ideal"]["measurement"]
    )
    for arm in ("ideal", "finite"):
        f = d["fits"][arm]["measured"]
        assert abs(f["phase"] - 0.7) < 4 * f["phase_se"]
    # Reproduce the single stream exactly; arm/setting blocks do not reuse draws.
    rng = p["seed"]
    seeds = []
    for _ in range(p["points"] * 3):
        seeds.append(rng)
        for _ in range(p["shots"]):
            rng = (1664525 * rng + 1013904223) % 2**32
    assert [
        r["arms"][a]["measurement"]["seed"] for r in d["records"] for a in readout.ARMS
    ] == seeds


def test_phase_uncertainty_empirical_scatter():
    # Many independent count experiments of analytic binomial fringes, not a solver self-check.
    rng = np.random.default_rng(87)
    phases, uncertainties = [], []
    for _ in range(250):
        rows = []
        for k in range(12):
            alpha = 2 * np.pi * k / 12
            counts = np.bincount(rng.binomial(40, (1 + np.cos(0.7 - alpha)) / 2, 256), minlength=41)
            rows.append(dict(alpha=alpha, **readout.statistics(counts, 40)))
        f = readout.fit(rows)
        phases.append(f["phase"])
        uncertainties.append(f["phase_se"])
    ratio = np.std(phases, ddof=1) / np.mean(uncertainties)
    assert 0.85 < ratio < 1.15
    assert abs(np.mean(phases) - 0.7) < 0.002


@pytest.mark.parametrize(
    "key,value",
    [
        ("points", 7),
        ("points", 8.5),
        ("shots", 15),
        ("seed", -1),
        ("pulse_j_hz", 0),
        ("hold_ms", -1),
        ("duration_error", 0.51),
        ("echo", 1),
    ],
)
def test_invalid_inputs_rejected_in_both_implementations(key, value):
    p = plan(**{key: value})
    with pytest.raises(ValueError):
        readout.validate(p)
    assert js("try{Readout.validate(data);console.log(false)}catch(e){console.log(true)}", p)


@pytest.mark.parametrize("part", ["counts", "state", "phase", "plan", "convention", "status"])
def test_tamper_detection(part):
    d = report(plan())
    bad = copy.deepcopy(d)
    if part == "counts":
        bad["records"][0]["arms"]["ideal"]["measurement"]["counts"][0] += 1
    elif part == "state":
        bad["records"][0]["arms"]["finite"]["state"]["real"][0] += 0.01
    elif part == "phase":
        bad["fits"]["ideal"]["measured"]["phase"] += 0.1
    elif part == "plan":
        bad["plan"]["duration_error"] = 0.4
    elif part == "convention":
        bad["convention"] = "incorrect"
    else:
        bad["records"].pop()
    with pytest.raises(ValueError):
        verify_export(bad)


def test_partial_scan_has_no_phase_fit_and_replays():
    d = report(plan(), 3)
    assert d["fits"] is None
    assert verify_export(d)["settings_verified"] == 3
