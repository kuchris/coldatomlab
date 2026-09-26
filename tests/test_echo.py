import copy
import json
import subprocess

import numpy as np
import pytest
from scipy.linalg import expm

from coldatomlab.echo import aggregate, checkpoints, evolve, ideal, validate
from coldatomlab.preparation import recipes
from coldatomlab.replay import verify_export
from coldatomlab.twomode import initial_state
from coldatomlab.twomode import validate as base_config


def plan(**kwargs):
    return (
        dict(
            base=base_config(
                dict(
                    atoms=12, left_fraction=0.5, tunnelling_hz=0, interaction_hz=0, duration_ms=500
                )
            ),
            phase_half_range=0,
            bias_half_range_hz=2,
            preparations=4,
            seed=17,
        )
        | kwargs
    )


def js(code, data):
    result = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "require('./coldatomlab/web/preparation.js');"
            "require('./coldatomlab/web/echo.js');"
            "const data=JSON.parse(require('fs').readFileSync(0,'utf8'));" + code,
        ],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(result.stdout)


def report(p):
    return js(
        "const p=Echo.validate(data),ref=Echo.ideal(p);"
        "console.log(JSON.stringify(Echo.report(p,ref,Preparation.recipes(p).map(Echo.evolve),'complete')));",
        p,
    )


def field(state):
    return np.array(state["real"]) + 1j * np.array(state["imag"])


def q(state):
    return state["coherence_real"] + 1j * state["coherence_imag"]


@pytest.mark.parametrize(
    "config",
    [
        {},
        dict(interaction_hz=1, duration_ms=250),
        dict(initial="gaussian", sigma=0.4, phase=2.9, left_fraction=0.7),
        dict(initial="fock", left_fraction=0.2),
        dict(atoms=3, left_fraction=0.8, bias_hz=-7),
        dict(atoms=100, interaction_hz=2, bias_hz=15, duration_ms=1000, phase=-3),
    ],
)
def test_independent_full_states_and_histories(config):
    p = plan(phase_half_range=1.3, bias_half_range_hz=5)
    p["base"].update(config)
    result = verify_export(report(p))
    assert result["verified"]
    assert result["maximum_complex_state_l2"] < 5e-8
    assert result["maximum_norm_drift"] < 1e-9


def test_static_bias_refocuses_paired_ensemble():
    p = plan(preparations=64)
    r = report(p)
    assert r == report(p)
    end = r["aggregate"]
    assert end["echo"]["history"][-1]["ensemble_coherence"] == pytest.approx(1, abs=1e-12)
    expected_free = abs(np.mean([np.exp(-1j * np.pi * x["bias_offset_hz"]) for x in r["records"]]))
    assert end["no_echo"]["history"][-1]["ensemble_coherence"] == pytest.approx(expected_free)
    assert expected_free < end["echo"]["history"][-1]["ensemble_coherence"]
    assert end["echo"]["history"][-1]["guide_coherence"] == pytest.approx(1)
    for record in r["records"]:
        assert record["no_echo"]["history"][:51] == record["echo"]["history"][:51]
        assert all(abs(row["coherence"] - 1) < 1e-12 for row in record["echo"]["history"])
        assert record["config"]["bias_hz"] == pytest.approx(record["bias_offset_hz"])
        assert (
            np.linalg.norm(field(record["echo"]["state"]) - initial_state(p["base"])[::-1]) < 1e-12
        )


@pytest.mark.parametrize("interaction", [0, 0.37, 1])
def test_final_field_cancels_bias_but_retains_interaction(interaction):
    p = plan(phase_half_range=0.8, bias_half_range_hz=3)
    p["base"].update(interaction_hz=interaction, duration_ms=237, left_fraction=0.7, bias_hz=4)
    r = report(p)
    for record in r["records"]:
        c = record["config"]
        m = np.arange(c["atoms"] + 1) - c["atoms"] / 2
        expected = initial_state(c)[::-1] * np.exp(-2j * np.pi * interaction * m**2 * 0.237)
        assert np.linalg.norm(field(record["echo"]["state"]) - expected) < 1e-11
        assert record["echo"]["state"]["mean_left"] == pytest.approx(c["atoms"] * 0.3)


def test_interaction_example_does_not_refocus_coherence():
    p = plan()
    p["base"].update(interaction_hz=1, duration_ms=250)
    r = report(p)
    for arm in ("no_echo", "echo"):
        for row in r["aggregate"][arm]["history"]:
            analytic = abs(np.cos(2 * np.pi * row["time_ms"] / 1000)) ** 11
            assert row["mean_individual_coherence"] == pytest.approx(analytic, abs=1e-12)
        assert r["aggregate"][arm]["history"][-1]["ensemble_coherence"] < 1e-12
        assert r["records"][0][arm]["state"]["phase"] is None


@pytest.mark.parametrize("initial", ["coherent", "gaussian", "fock"])
def test_finite_sample_complex_factorization_and_uniform_guides(initial):
    p = plan(phase_half_range=1.2, bias_half_range_hz=3, preparations=16)
    p["base"].update(initial=initial, interaction_hz=0.4, phase=0.7, duration_ms=331)
    r = report(p)
    alpha = np.array([s["phase_offset"] for s in r["records"]])
    beta = np.array([s["bias_offset_hz"] for s in r["records"]])
    for arm in ("no_echo", "echo"):
        for i, row in enumerate(r["aggregate"][arm]["history"]):
            t = row["time_ms"] / 1000
            sign = -1 if row["pulse_applied"] else 1
            effective = t - (0.331 if row["pulse_applied"] else 0)
            finite = np.mean(np.exp(1j * (sign * alpha - 2 * np.pi * beta * effective)))
            ref = r["ideal"][arm]["history"][i]
            assert q(row) == pytest.approx(q(ref) * finite, abs=1e-11)
            guide = ref["coherence"] * abs(np.sinc(1.2 / np.pi) * np.sinc(6 * effective))
            assert row["guide_coherence"] == pytest.approx(guide, abs=1e-12)


def test_initial_phase_spread_remains_at_echo():
    p = plan(phase_half_range=np.pi / 2, preparations=64)
    r = report(p)
    initial = r["aggregate"]["echo"]["history"][0]
    final = r["aggregate"]["echo"]["history"][-1]
    assert q(final) == pytest.approx(q(initial).conjugate(), abs=1e-12)
    assert 0.3 < final["ensemble_coherence"] < 0.9
    assert final["guide_coherence"] == pytest.approx(2 / np.pi)


def test_pulse_norm_population_coherence_energy_and_inverse():
    p = plan()
    p["base"].update(left_fraction=0.7, bias_hz=3, interaction_hz=0.6, phase=1.2)
    r = report(p)["records"][0]
    before, after = r["pulse_before"], r["pulse_after"]
    assert after["norm"] == pytest.approx(before["norm"], abs=1e-12)
    assert field(after) == pytest.approx(field(before)[::-1], abs=1e-12)
    assert after["probability"] == pytest.approx(before["probability"][::-1], abs=1e-12)
    assert q(after) == pytest.approx(q(before).conjugate(), abs=1e-12)
    assert after["energy_hz"] - before["energy_hz"] == pytest.approx(
        2 * r["config"]["bias_hz"] * (before["mean_left"] - p["base"]["atoms"] / 2)
    )
    twice = js(
        "const s={r:data.real,im:data.imag},t=Echo.swap(Echo.swap(s));"
        "console.log(JSON.stringify({real:Array.from(t.r),imag:Array.from(t.im)}));",
        before,
    )
    assert field(twice) == pytest.approx(field(before), abs=1e-15)


@pytest.mark.parametrize("atoms", [2, 3, 8])
def test_swap_is_pi_rotation_up_to_fixed_global_phase(atoms):
    off = np.sqrt(np.arange(1, atoms + 1) * np.arange(atoms, 0, -1)) / 2
    jx = np.diag(off, 1) + np.diag(off, -1)
    rotation = expm(-1j * np.pi * jx)
    assert np.max(abs(rotation - (-1j) ** atoms * np.eye(atoms + 1)[::-1])) < 1e-14


def test_checkpoints_and_exact_pulse_boundary():
    p = plan()
    p["base"]["duration_ms"] = 123.456
    r = report(p)
    rows = r["records"][0]["echo"]["history"]
    assert len(rows) == 102
    assert rows[50]["time_ms"] == rows[51]["time_ms"] == 61.728
    assert rows[50]["pulse_applied"] is False and rows[51]["pulse_applied"] is True
    assert rows[-1]["time_ms"] == 123.456
    assert [x["time_ms"] for x in checkpoints(123.456)] == [x["time_ms"] for x in rows]
    assert q(rows[51]) == pytest.approx(q(rows[50]).conjugate(), abs=1e-12)


def test_zero_variation_and_count_mixture():
    p = plan(phase_half_range=0, bias_half_range_hz=0)
    r = report(p)
    for arm in ("no_echo", "echo"):
        for row in r["aggregate"][arm]["history"]:
            assert row["ensemble_coherence"] == pytest.approx(row["ideal_coherence"], abs=1e-12)
            assert row["total_variance"] == pytest.approx(3, abs=1e-12)
        assert r["aggregate"][arm]["probability"] == pytest.approx(
            r["ideal"][arm]["state"]["probability"]
        )


def test_cancelled_prefix_replays():
    p = plan()
    r = report(p)
    r["status"] = "cancelled"
    r["records"] = r["records"][:1]
    reference = ideal(p)
    records = [evolve(recipes(p)[0])]
    r["aggregate"] = aggregate(p, reference, records)
    assert verify_export(r)["paired_preparations_verified"] == 1


@pytest.mark.parametrize(
    "path,value",
    [
        (("convention",), "flip phase"),
        (("status",), "running"),
        (("plan", "seed"), 18),
        (("records", 0, "bias_offset_hz"), 0),
        (("records", 0, "pulse_after", "real", 3), 0.9),
        (("records", 0, "echo", "state", "imag", 2), 0.8),
        (("records", 0, "echo", "history", 51, "pulse_applied"), False),
        (("records", 0, "echo", "history", 51, "time_ms"), 251),
        (("records", 0, "no_echo", "history", 40, "norm"), 0.99),
        (("aggregate", "echo", "history", 101, "guide_coherence"), 0.9),
        (("aggregate", "no_echo", "probability", 0), 0.5),
        (("ideal", "echo", "state", "coherence"), 0.5),
    ],
)
def test_tampering_rejected(path, value):
    r = report(plan())
    obj = r
    for key in path[:-1]:
        obj = obj[key]
    obj[path[-1]] = value
    with pytest.raises(ValueError):
        verify_export(r)


@pytest.mark.parametrize(
    "key,value",
    [("phase_half_range", -1), ("bias_half_range_hz", 6), ("preparations", 1), ("seed", 2**32)],
)
def test_invalid_settings_rejected_in_both_languages(key, value):
    p = plan(**{key: value})
    with pytest.raises(ValueError):
        validate(p)
    assert js("try{Echo.validate(data);console.log(false)}catch(e){console.log(true)}", p)


def test_nonzero_tunnelling_rejected_not_removed():
    p = plan()
    p["base"]["tunnelling_hz"] = 1
    saved = copy.deepcopy(p)
    with pytest.raises(ValueError, match="J=0"):
        validate(p)
    assert js("try{Echo.validate(data);console.log(false)}catch(e){console.log(true)}", p)
    assert p == saved
