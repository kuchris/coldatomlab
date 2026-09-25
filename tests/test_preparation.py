import copy
import json
import subprocess

import numpy as np
import pytest

from coldatomlab.preparation import aggregate, evolve, ideal, recipes, validate
from coldatomlab.replay import verify_export
from coldatomlab.twomode import validate as base_config


def plan(**kwargs):
    return (
        dict(
            base=base_config(
                dict(
                    atoms=12, left_fraction=0.5, tunnelling_hz=0, interaction_hz=0, duration_ms=500
                )
            ),
            phase_half_range=0.3,
            bias_half_range_hz=1,
            preparations=4,
            seed=17,
        )
        | kwargs
    )


def js(code, data):
    p = subprocess.run(
        [
            "node",
            "-e",
            "require('./coldatomlab/web/twomode.js');"
            "require('./coldatomlab/web/preparation.js');"
            "const data=JSON.parse(require('fs').readFileSync(0,'utf8'));" + code,
        ],
        input=json.dumps(data),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(p.stdout)


def report(p):
    return js(
        "const p=Preparation.validate(data),ideal=Preparation.ideal(p);"
        "console.log(JSON.stringify(Preparation.report(p,ideal,"
        "Preparation.recipes(p).map(Preparation.evolve),'complete')));",
        p,
    )


@pytest.mark.parametrize(
    "config",
    [
        dict(),
        dict(interaction_hz=1),
        dict(tunnelling_hz=2, interaction_hz=0.4, bias_hz=0.7),
        dict(initial="gaussian", sigma=0.5, phase=3),
        dict(initial="fock"),
        dict(atoms=3, left_fraction=0.8, tunnelling_hz=1),
        dict(atoms=100, tunnelling_hz=20, interaction_hz=2, bias_hz=15, phase=-3, duration_ms=1000),
    ],
)
def test_independent_states_histories_and_mixture(config):
    p = plan()
    p["base"].update(config)
    result = verify_export(report(p))
    assert result["verified"]
    assert result["maximum_complex_state_l2"] < 5e-8


def test_zero_noise_recovers_reference():
    r = report(plan(phase_half_range=0, bias_half_range_hz=0))
    for row in r["aggregate"]["history"]:
        assert row["ensemble_coherence"] == pytest.approx(row["ideal_coherence"], abs=1e-12)
        assert row["mean_individual_coherence"] == pytest.approx(row["ideal_coherence"], abs=1e-12)
        assert row["between_variance"] < 1e-20
    assert r["aggregate"]["probability"] == pytest.approx(r["ideal"]["state"]["probability"])


@pytest.mark.parametrize(
    "interaction,initial", [(0, "coherent"), (1, "coherent"), (0.4, "gaussian"), (1, "fock")]
)
def test_exact_isolated_finite_ensemble_factorization(interaction, initial):
    p = plan(preparations=16, phase_half_range=1.3, bias_half_range_hz=2)
    p["base"].update(interaction_hz=interaction, initial=initial, bias_hz=0.4)
    data = report(p)
    for i, row in enumerate(data["aggregate"]["history"]):
        t = row["time_ms"] / 1000
        shifts = np.array(
            [r["phase_offset"] - 2 * np.pi * r["bias_offset_hz"] * t for r in data["records"]]
        )
        base = data["ideal"]["history"][i]
        reference = base["coherence_real"] + 1j * base["coherence_imag"]
        actual = row["coherence_real"] + 1j * row["coherence_imag"]
        assert actual == pytest.approx(reference * np.mean(np.exp(1j * shifts)), abs=2e-12)
        assert row["mean_individual_coherence"] == pytest.approx(base["coherence"], abs=2e-12)
        expected_guide = abs(reference * np.sinc(1.3 / np.pi) * np.sinc(4 * t))
        assert row["guide_coherence"] == pytest.approx(expected_guide, abs=2e-12)
        assert row["between_variance"] < 1e-20
    assert data["aggregate"]["probability"] == pytest.approx(
        data["ideal"]["state"]["probability"], abs=1e-12
    )


def test_conditional_coherence_is_not_ensemble_coherence():
    d = report(plan(preparations=64))
    final = d["aggregate"]["history"][-1]
    assert final["mean_individual_coherence"] == pytest.approx(1)
    assert final["ensemble_coherence"] < 0.25
    assert final["guide_coherence"] < 1e-15
    assert final["within_variance"] == pytest.approx(3)
    assert final["between_variance"] < 1e-20


def test_coupled_number_variance_decomposition():
    p = plan(preparations=8, phase_half_range=1.5, bias_half_range_hz=2)
    p["base"].update(tunnelling_hz=2, duration_ms=130)
    d = report(p)
    row = d["aggregate"]["history"][-1]
    probability = np.array(d["aggregate"]["probability"])
    n = np.arange(len(probability))
    mean = n @ probability
    variance = ((n - mean) ** 2) @ probability
    assert row["total_variance"] == pytest.approx(variance, abs=1e-10)
    assert row["between_variance"] > 0.1
    assert row["guide_coherence"] is None
    assert row["ensemble_coherence"] <= row["mean_individual_coherence"] + 1e-12


def test_rng_recipe_parity_moments_and_sampling_convergence():
    p = plan(preparations=128, phase_half_range=2, bias_half_range_hz=3)
    a = recipes(p)
    b = js("console.log(JSON.stringify(Preparation.recipes(data)))", p)
    for left, right in zip(a, b, strict=True):
        assert left["phase_offset"] == right["phase_offset"]
        assert left["bias_offset_hz"] == right["bias_offset_hz"]
        assert left["config"]["phase"] == pytest.approx(right["config"]["phase"], abs=1e-14)
    assert a != recipes(p | dict(seed=18))
    offsets = np.array(
        [
            [r["phase_offset"], r["bias_offset_hz"]]
            for seed in range(64)
            for r in recipes(p | dict(seed=seed))
        ]
    )
    # A finite random ensemble has sampling error; use a five-standard-error bound.
    assert np.all(abs(offsets.mean(axis=0)) < 5 * np.sqrt(np.array([4 / 3, 3]) / len(offsets)))
    assert offsets.var(axis=0) == pytest.approx([4 / 3, 3], rel=0.035)
    assert abs(np.corrcoef(offsets.T)[0, 1]) < 0.035
    errors = []
    target = np.sinc(2 / np.pi) * np.sinc(6 * 0.2)
    for count in (8, 128):
        estimates = [
            np.mean(
                [
                    np.exp(1j * (r["phase_offset"] - 2 * np.pi * 0.2 * r["bias_offset_hz"]))
                    for r in recipes(p | dict(preparations=count, seed=seed))
                ]
            )
            for seed in range(64)
        ]
        errors.append(np.mean(abs(np.array(estimates) - target) ** 2))
    assert errors[1] < errors[0] / 8


@pytest.fixture(scope="module")
def exported():
    return report(plan())


def test_cancelled_prefix_replays(exported):
    d = copy.deepcopy(exported)
    d["records"] = d["records"][:2]
    d["status"] = "cancelled"
    d["aggregate"] = aggregate(d["plan"], d["ideal"], d["records"])
    assert verify_export(d)["preparations_verified"] == 2


@pytest.mark.parametrize(
    "change",
    [
        "seed",
        "offset",
        "order",
        "field",
        "history",
        "aggregate",
        "probability",
        "guide",
        "status",
        "norm",
        "nan",
        "convention",
    ],
)
def test_tampering_is_rejected(exported, change):
    d = copy.deepcopy(exported)
    r = d["records"][0]
    if change == "seed":
        d["plan"]["seed"] += 1
    if change == "offset":
        r["phase_offset"] += 0.1
    if change == "order":
        d["records"].reverse()
    if change == "field":
        r["state"]["real"][3] += 0.01
    if change == "history":
        r["history"][10]["coherence_real"] += 0.1
    if change == "aggregate":
        d["aggregate"]["history"][-1]["ensemble_coherence"] += 0.1
    if change == "probability":
        d["aggregate"]["probability"][3] += 0.1
    if change == "guide":
        d["aggregate"]["history"][-1]["guide_coherence"] = 0.5
    if change == "status":
        d["records"].pop()
    if change == "norm":
        r["state"]["norm"] = 1.1
    if change == "nan":
        d["aggregate"]["history"][0]["within_variance"] = float("nan")
    if change == "convention":
        d["convention"] = "averaged wavefunctions"
    with pytest.raises(ValueError):
        verify_export(d)


@pytest.mark.parametrize(
    "updates",
    [
        dict(phase_half_range=-1),
        dict(phase_half_range=4),
        dict(bias_half_range_hz=6),
        dict(preparations=1),
        dict(preparations=129),
        dict(preparations=2.5),
        dict(seed=-1),
        dict(seed=2**32),
        dict(seed=True),
        dict(extra=1),
    ],
)
def test_invalid_noise_plan(updates):
    p = plan(**updates)
    with pytest.raises(ValueError):
        validate(p)
    assert js(
        "let error=false;try{Preparation.validate(data)}catch(e){error=true};console.log(error)", p
    )


def test_bias_samples_are_not_clipped():
    p = plan()
    p["base"]["bias_hz"] = 20
    with pytest.raises(ValueError):
        validate(p)
    assert js(
        "let error=false;try{Preparation.validate(data)}catch(e){error=true};console.log(error)", p
    )


def test_python_aggregate_normalized():
    p = plan(preparations=2)
    a = aggregate(p, ideal(p), [evolve(r) for r in recipes(p)])
    assert sum(a["probability"]) == pytest.approx(1)
