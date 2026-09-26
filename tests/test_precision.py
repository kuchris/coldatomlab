import copy
import json
import math
import subprocess

import numpy as np
import pytest

from coldatomlab import precision, readout
from coldatomlab.replay import verify_export
from coldatomlab.twomode import validate


def plan(**kwargs):
    return (
        dict(
            readout=dict(
                base=validate(dict(atoms=4, left_fraction=0.5, phase=0.7, tunnelling_hz=0)),
                hold_ms=0,
                echo=False,
                pulse_j_hz=10,
                duration_error=0,
                points=8,
                shots=16,
                seed=17,
            ),
            more_atoms=8,
            more_shots=32,
            repetitions=20,
        )
        | kwargs
    )


def js(code, data):
    proc = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "require('./coldatomlab/web/preparation.js');require('./coldatomlab/web/echo.js');"
            "require('./coldatomlab/web/readout.js');require('./coldatomlab/web/precision.js');"
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
        "const p=Precision.validate(data.p),models=Precision.configs(p).map(Precision.modelCase),"
        "n=data.count??p.repetitions,rs=Array.from({length:n},(_,i)=>Precision.trial(p,models,i));"
        "console.log(JSON.stringify(Precision.report(p,models,rs,n===p.repetitions?'complete':'cancelled')));",
        dict(p=p, count=count),
    )


@pytest.mark.parametrize(
    "seed,steps", [(0, 0), (0, 1), (17, 100), (2**32 - 1, 65537), (18, 15999999)]
)
def test_lcg_jump_matches_sequential_stream(seed, steps):
    value = seed
    for _ in range(steps):
        value = (1664525 * value + 1013904223) % 2**32
    assert precision.jump(seed, steps) == value
    assert js("console.log(Precision.jump(data[0],data[1]));", [seed, steps]) == value


@pytest.mark.parametrize(
    "config,settings",
    [
        ({}, {}),
        (dict(initial="fock"), {}),
        (
            dict(initial="gaussian", sigma=0.5, interaction_hz=0.3, bias_hz=8),
            dict(hold_ms=175, echo=True, duration_error=0.2),
        ),
        (dict(phase=math.pi - 0.001, bias_hz=-10), dict(hold_ms=60, pulse_j_hz=0.5)),
        (dict(atoms=99, interaction_hz=2, bias_hz=20), dict(hold_ms=1000)),
    ],
)
def test_independent_model_counts_and_summary_replay(config, settings):
    p = plan()
    p["readout"]["base"].update(config)
    p["readout"].update(settings)
    if p["readout"]["base"]["atoms"] == 99:
        p["more_atoms"] = 100
    result = verify_export(report(p, 3))
    assert result["maximum_complex_state_l2"] < 5e-8
    assert result["maximum_norm_drift"] < 1e-9


def test_every_arm_setting_case_trial_uses_fresh_blocks():
    p = plan()
    d = report(p, 3)
    expected = p["readout"]["seed"]
    for r in d["records"]:
        for model in d["models"]:
            for k in range(model["plan"]["points"]):
                for a in precision.ARMS:
                    sample = r["cases"][model["name"]][a]["measurements"][k]
                    assert sample["seed"] == expected
                    assert sum(sample["counts"]) == model["plan"]["shots"]
                    expected = precision.jump(expected, model["plan"]["shots"])
    assert report(p, 3) == d
    p["readout"]["seed"] = 18
    assert report(p, 3)["records"] != d["records"]


def test_scatter_matches_se_and_analytic_resource_scaling():
    p = plan(more_atoms=80, more_shots=256, repetitions=200)
    p["readout"].update(points=12, shots=64)
    p["readout"]["base"]["atoms"] = 20
    d = report(p)
    scatter = []
    for m in d["models"]:
        s = d["summary"][m["name"]]["ideal"]
        guide = m["ideal_scatter_guide"]
        assert s["resolved"] == 200
        assert 0.8 < s["circular_scatter"] / guide < 1.2
        assert 0.8 < s["scatter_over_se"] < 1.2
        assert 0.57 < s["within_one_se"] < 0.79
        assert abs(s["circular_bias"]) < 0.25 * guide
        scatter.append(s["circular_scatter"])
    assert 0.38 < scatter[1] / scatter[0] < 0.62
    assert 0.38 < scatter[2] / scatter[0] < 0.62
    # K>=8 Fourier grid: delta-method variance = 3/(2 N K S), not the optimal local SQL.
    K, S, N = 12, 64, 20
    rows = [
        dict(
            alpha=2 * np.pi * k / K,
            z=np.cos(0.7 - 2 * np.pi * k / K),
            variance_z_mean=np.sin(0.7 - 2 * np.pi * k / K) ** 2 / (N * S),
        )
        for k in range(K)
    ]
    assert readout.fit(rows)["phase_se"] == pytest.approx(math.sqrt(3 / (2 * N * K * S)))


def test_biased_pulse_can_be_precise_but_wrong():
    p = plan(more_atoms=80, more_shots=256, repetitions=100)
    p["readout"].update(points=12, shots=64, duration_error=0.2)
    p["readout"]["base"].update(atoms=20, bias_hz=8)
    d = report(p)
    for name in precision.CASES:
        s = d["summary"][name]["finite"]
        assert s["resolved"] == 100
        assert abs(s["circular_bias"]) > 0.4
        assert abs(s["circular_bias"] - s["model_bias"]) < 0.01
        assert s["circular_scatter"] < 0.03
        assert s["wrapped_rmse"] > 0.4
        assert s["within_one_se"] == 0
    assert (
        d["summary"]["more_shots"]["finite"]["circular_scatter"]
        < d["summary"]["baseline"]["finite"]["circular_scatter"]
    )


def test_circular_summary_crosses_branch_cut_without_false_large_scatter():
    truth = math.pi - 0.002
    model = dict(
        name="baseline", source=dict(phase=truth), model_fits=dict(ideal=dict(phase=truth))
    )
    phases = [truth - 0.01, precision.wrap(truth + 0.01), None]
    records = [
        dict(
            cases=dict(
                baseline=dict(
                    ideal=dict(fit=dict(phase=x, phase_se=0.01 if x is not None else None))
                )
            )
        )
        for x in phases
    ]
    result = precision.summary(model, records, "ideal")
    check = js(
        "console.log(JSON.stringify(Precision.summary(data.m,data.rs,'ideal')));",
        dict(m=model, rs=records),
    )
    for key in result:
        if isinstance(result[key], float):
            assert check[key] == pytest.approx(result[key], abs=1e-10)
        else:
            assert check[key] == result[key]
    assert result["resolved"] == 2 and result["unresolved"] == 1
    assert abs(result["circular_bias"]) < 1e-12
    assert result["circular_scatter"] == pytest.approx(0.01, abs=1e-6)
    assert result["wrapped_rmse"] == pytest.approx(0.01)


def test_missing_phase_and_partial_prefix_are_not_zero_errors():
    p = plan()
    p["readout"]["base"]["initial"] = "fock"
    d = report(p, 2)
    for m in d["models"]:
        assert m["ideal_scatter_guide"] is None
        for a in precision.ARMS:
            s = d["summary"][m["name"]][a]
            assert s["circular_bias"] is None and s["wrapped_rmse"] is None
    assert verify_export(d)["repetitions_verified"] == 2
    one = report(plan(), 1)
    assert one["summary"]["baseline"]["ideal"]["circular_scatter"] is None


@pytest.mark.parametrize(
    "key,value",
    [
        ("more_atoms", 4),
        ("more_atoms", 101),
        ("more_shots", 16),
        ("repetitions", 19),
        ("repetitions", 301),
        ("repetitions", 20.5),
    ],
)
def test_invalid_comparisons_rejected(key, value):
    p = plan(**{key: value})
    with pytest.raises(ValueError):
        precision.validate(p)
    assert js("try{Precision.validate(data);console.log(false)}catch(e){console.log(true)}", p)


def test_workload_guard_and_unknown_keys():
    p = plan(more_shots=4096, repetitions=300)
    p["readout"].update(points=32, shots=4000)
    with pytest.raises(ValueError, match="16 million"):
        precision.validate(p)
    assert js(
        "try{Precision.validate(data);console.log(false)}catch(e){console.log(e.message.includes('16 million'))}",
        p,
    )
    with pytest.raises(ValueError):
        precision.validate(plan(extra=True))


@pytest.mark.parametrize("part", ["seed", "counts", "fit", "summary", "model", "recipe", "status"])
def test_export_tampering(part):
    d = report(plan(), 2)
    bad = copy.deepcopy(d)
    arm = bad["records"][0]["cases"]["baseline"]["ideal"]
    if part == "seed":
        arm["measurements"][0]["seed"] += 1
    elif part == "counts":
        arm["measurements"][0]["counts"][0] += 1
    elif part == "fit":
        arm["fit"]["contrast"] += 0.1
    elif part == "summary":
        bad["summary"]["baseline"]["ideal"]["resolved"] = 100
    elif part == "model":
        bad["models"][0]["points"][0]["arms"]["finite"]["real"][0] += 0.1
    elif part == "recipe":
        bad["plan"]["readout"]["duration_error"] = 0.3
    else:
        bad["status"] = "complete"
    with pytest.raises(ValueError):
        verify_export(bad)


def test_prior_readout_version_remains_replayable():
    p = plan()["readout"]
    s = readout.incoming(p)
    d = readout.report(p, s, [readout.point(p, s, i) for i in range(p["points"])], "complete")
    d["version"] = "0.14.0"
    assert verify_export(d)["verified"]
