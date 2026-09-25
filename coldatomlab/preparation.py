"""Independent replay of fixed-N preparations with uniform phase/bias variation."""

import math

import numpy as np

from .twomode import Reference, _compare
from .twomode import validate as validate_base

HISTORY_KEYS = (
    "time_ms",
    "mean_left",
    "variance_left",
    "coherence",
    "coherence_real",
    "coherence_imag",
    "norm",
    "energy_hz",
)


def validate(plan):
    if set(plan) != {"base", "phase_half_range", "bias_half_range_hz", "preparations", "seed"}:
        raise ValueError("Unknown or missing preparation parameter.")
    p = dict(plan, base=validate_base(plan["base"]))
    for key, lo, hi in [
        ("phase_half_range", 0, math.pi),
        ("bias_half_range_hz", 0, 5),
        ("preparations", 2, 128),
        ("seed", 0, 2**32 - 1),
    ]:
        v = p[key]
        if (
            isinstance(v, bool)
            or not isinstance(v, (float, int))
            or not math.isfinite(v)
            or not lo <= v <= hi
        ):
            raise ValueError(f"Invalid {key}.")
    if type(p["preparations"]) is not int or type(p["seed"]) is not int:
        raise ValueError("Count and seed must be integers.")
    if abs(p["base"]["bias_hz"]) + p["bias_half_range_hz"] > 20:
        raise ValueError("Bias variation exceeds the model limits.")
    return p


def recipes(plan):
    p = validate(plan)
    rng = p["seed"]
    result = []
    for index in range(p["preparations"]):
        rng = (1664525 * rng + 1013904223) % 2**32
        phase_offset = (2 * (rng + 0.5) / 2**32 - 1) * p["phase_half_range"]
        rng = (1664525 * rng + 1013904223) % 2**32
        bias_offset = (2 * (rng + 0.5) / 2**32 - 1) * p["bias_half_range_hz"]
        phase = p["base"]["phase"] + phase_offset
        config = dict(
            p["base"],
            phase=math.atan2(math.sin(phase), math.cos(phase)),
            bias_hz=p["base"]["bias_hz"] + bias_offset,
        )
        result.append(
            dict(index=index, phase_offset=phase_offset, bias_offset_hz=bias_offset, config=config)
        )
    return result


def evolve(recipe):
    ref = Reference(recipe["config"])
    history = []
    for i in range(101):
        state = ref.at(ref.config["duration_ms"] * i / 100)
        history.append({k: state[k] for k in HISTORY_KEYS})
    return dict(recipe, state=state, history=history)


def ideal(plan):
    return evolve(dict(index=-1, phase_offset=0, bias_offset_hz=0, config=plan["base"]))


def aggregate(plan, reference, records):
    if not records:
        return None
    history = []
    for i, ref in enumerate(reference["history"]):
        rows = [r["history"][i] for r in records]

        def mean(key):
            return float(np.mean([r[key] for r in rows]))

        mean_left = mean("mean_left")
        re, im = mean("coherence_real"), mean("coherence_imag")
        within = mean("variance_left")
        between = float(np.mean([(r["mean_left"] - mean_left) ** 2 for r in rows]))
        guide = None
        if plan["base"]["tunnelling_hz"] == 0:
            guide = float(
                ref["coherence"]
                * abs(
                    np.sinc(plan["phase_half_range"] / np.pi)
                    * np.sinc(2 * plan["bias_half_range_hz"] * ref["time_ms"] / 1000)
                )
            )
        history.append(
            dict(
                time_ms=ref["time_ms"],
                mean_left=mean_left,
                coherence_real=re,
                coherence_imag=im,
                ensemble_coherence=math.hypot(re, im),
                mean_individual_coherence=mean("coherence"),
                ideal_coherence=ref["coherence"],
                guide_coherence=guide,
                within_variance=within,
                between_variance=between,
                total_variance=within + between,
                mean_norm=mean("norm"),
            )
        )
    return dict(
        count=len(records),
        history=history,
        probability=np.mean([r["state"]["probability"] for r in records], axis=0).tolist(),
    )


def compare_record(saved, expected):
    if set(saved) != set(expected):
        raise ValueError("Invalid realization fields.")
    _compare(
        {k: saved[k] for k in ("index", "phase_offset", "bias_offset_hz")},
        {k: expected[k] for k in ("index", "phase_offset", "bias_offset_hz")},
        "Recipe",
    )
    # Configuration includes a string state name, so compare that separately.
    if saved["config"].get("initial") != expected["config"]["initial"]:
        raise ValueError("Initial state differs.")
    _compare(
        {k: v for k, v in saved["config"].items() if k != "initial"},
        {k: v for k, v in expected["config"].items() if k != "initial"},
        "Config",
    )
    _compare(saved["state"], expected["state"], "Final realization state")
    psi = np.asarray(saved["state"]["real"]) + 1j * np.asarray(saved["state"]["imag"])
    ref = np.asarray(expected["state"]["real"]) + 1j * np.asarray(expected["state"]["imag"])
    error = float(np.linalg.norm(psi - ref))
    if error > 5e-8 or abs(saved["state"]["norm"] - 1) > 1e-9:
        raise ValueError("Realization field or norm tolerance exceeded.")
    if len(saved["history"]) != 101:
        raise ValueError("Realization history length differs.")
    for a, b in zip(saved["history"], expected["history"], strict=True):
        _compare(a, b, "Realization history")
    return error


def verify_export(data):
    if data.get("schema") != "coldatomlab-preparation-v1" or data.get("convention") != (
        "fixed-N density mixture; independent uniform offsets; bias constant per realization"
    ):
        raise ValueError("Unknown ensemble convention.")
    plan = validate(data["plan"])
    count = len(data["records"])
    if data["status"] not in ("complete", "cancelled") or not 1 <= count <= plan["preparations"]:
        raise ValueError("Invalid completed-prefix status.")
    if data["status"] == "complete" and count != plan["preparations"]:
        raise ValueError("Incomplete ensemble marked complete.")
    reference = ideal(plan)
    errors = [compare_record(data["ideal"], reference)]
    records = []
    for saved, recipe in zip(data["records"], recipes(plan)[:count], strict=True):
        expected = evolve(recipe)
        errors.append(compare_record(saved, expected))
        records.append(expected)
    expected = aggregate(plan, reference, records)
    saved = data["aggregate"]
    if set(saved) != set(expected) or len(saved["history"]) != 101:
        raise ValueError("Invalid aggregate fields.")
    _compare(
        {k: saved[k] for k in ("count", "probability")},
        {k: expected[k] for k in ("count", "probability")},
        "Mixture",
    )
    for a, b in zip(saved["history"], expected["history"], strict=True):
        _compare(a, b, "Aggregate history")
    return dict(
        verified=True,
        preparations_verified=count,
        status=data["status"],
        maximum_complex_state_l2=max(errors),
        history_rows=101,
        reference="Independent NumPy states and density-mixture observables; no detector model",
    )
