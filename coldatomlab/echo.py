"""Independent spectral reference for paired isolated holds and a midpoint mode swap."""

import math

import numpy as np

from . import preparation
from .twomode import Reference, _compare, diagnostics

CONVENTION = (
    "J=0; H/h=U(n-N/2)^2-bias(n-N/2); midpoint S|n,N-n>=|N-n,n>; fixed-N pulse global phase omitted"
)


def validate(plan):
    p = preparation.validate(plan)
    if p["base"]["tunnelling_hz"] != 0:
        raise ValueError("Spin echo requires J=0 during both holds.")
    return p


def checkpoints(duration):
    times = [duration * i / 100 for i in range(101)]
    times.insert(51, duration / 2)
    return [dict(time_ms=t, pulse_applied=i >= 51) for i, t in enumerate(times)]


def evolve(recipe):
    ref = Reference(recipe["config"])
    c = ref.config
    if c["tunnelling_hz"] != 0:
        raise ValueError("Spin echo requires J=0.")
    v, energies = ref.vectors, ref.eigenvalues
    initial = v @ ref.coefficients
    half = c["duration_ms"] / 2

    def advance(state, time):
        return v @ (np.exp(-2j * np.pi * energies * time / 1000) * (v.T @ state))

    def observe(state, time):
        return dict(
            time_ms=time,
            real=state.real.tolist(),
            imag=state.imag.tolist(),
            **diagnostics(c, state),
        )

    before = advance(initial, half)
    swap_operator = np.eye(c["atoms"] + 1)[::-1]
    after = swap_operator @ before
    record = dict(
        **recipe,
        pulse_before=observe(before, half),
        pulse_after=observe(after, half),
        no_echo=dict(history=[]),
        echo=dict(history=[]),
    )
    for point in checkpoints(c["duration_ms"]):
        for arm in ("no_echo", "echo"):
            applied = arm == "echo" and point["pulse_applied"]
            time = point["time_ms"]
            psi = advance(after if applied else initial, time - half if applied else time)
            state = observe(psi, time)
            record[arm]["state"] = state
            record[arm]["history"].append(
                dict(**{k: state[k] for k in preparation.HISTORY_KEYS}, pulse_applied=applied)
            )
    return record


def ideal(plan):
    return evolve(dict(index=-1, phase_offset=0, bias_offset_hz=0, config=plan["base"]))


def aggregate(plan, reference, records):
    if not records:
        return None
    result = {}
    for arm in ("no_echo", "echo"):
        result[arm] = preparation.aggregate(plan, reference[arm], [r[arm] for r in records])
        for i, row in enumerate(result[arm]["history"]):
            row["pulse_applied"] = reference[arm]["history"][i]["pulse_applied"]
            effective = row["time_ms"] - (
                plan["base"]["duration_ms"] if row["pulse_applied"] else 0
            )
            row["guide_coherence"] = float(
                row["ideal_coherence"]
                * abs(
                    np.sinc(plan["phase_half_range"] / np.pi)
                    * np.sinc(2 * plan["bias_half_range_hz"] * effective / 1000)
                )
            )
    return result


def compare_tree(saved, expected, context="Echo"):
    """Strict structure plus the established absolute/phase-aware numeric tolerance."""
    if isinstance(expected, dict):
        if not isinstance(saved, dict) or set(saved) != set(expected):
            raise ValueError(f"{context}: fields differ.")
        for key, value in expected.items():
            if key == "phase":
                _compare({key: saved[key]}, {key: value}, context)
            else:
                compare_tree(saved[key], value, f"{context}.{key}")
    elif isinstance(expected, list):
        if not isinstance(saved, list) or len(saved) != len(expected):
            raise ValueError(f"{context}: lengths differ.")
        for i, (a, b) in enumerate(zip(saved, expected, strict=True)):
            compare_tree(a, b, f"{context}[{i}]")
    elif isinstance(expected, (str, bool)) or expected is None:
        if type(saved) is not type(expected) or saved != expected:
            raise ValueError(f"{context}: value differs.")
    elif (
        isinstance(saved, bool)
        or not isinstance(saved, (float, int))
        or not math.isfinite(saved)
        or abs(saved - expected) > 5e-8
    ):
        raise ValueError(f"{context}: value differs.")


def verify_export(data):
    if data.get("schema") != "coldatomlab-echo-v1" or data.get("convention") != CONVENTION:
        raise ValueError("Unknown echo convention.")
    plan = validate(data["plan"])
    count = len(data["records"])
    if data["status"] not in ("complete", "cancelled") or not 1 <= count <= plan["preparations"]:
        raise ValueError("Invalid completed-prefix status.")
    if data["status"] == "complete" and count != plan["preparations"]:
        raise ValueError("Incomplete comparison marked complete.")
    reference = ideal(plan)
    records = [evolve(recipe) for recipe in preparation.recipes(plan)[:count]]
    compare_tree(data["ideal"], reference)
    compare_tree(data["records"], records)
    compare_tree(data["aggregate"], aggregate(plan, reference, records))
    errors, drift = [], []
    for saved, expected in zip(
        [data["ideal"], *data["records"]], [reference, *records], strict=True
    ):
        for a, b in (
            (saved["pulse_before"], expected["pulse_before"]),
            (saved["pulse_after"], expected["pulse_after"]),
            (saved["no_echo"]["state"], expected["no_echo"]["state"]),
            (saved["echo"]["state"], expected["echo"]["state"]),
        ):
            psi = np.asarray(a["real"]) + 1j * np.asarray(a["imag"])
            oracle = np.asarray(b["real"]) + 1j * np.asarray(b["imag"])
            errors.append(float(np.linalg.norm(psi - oracle)))
            drift.append(abs(a["norm"] - 1))
        for arm in ("no_echo", "echo"):
            drift.extend(abs(row["norm"] - 1) for row in saved[arm]["history"])
    if max(errors) > 5e-8 or max(drift) > 1e-9:
        raise ValueError("Echo state or norm tolerance exceeded.")
    return dict(
        verified=True,
        paired_preparations_verified=count,
        status=data["status"],
        maximum_complex_state_l2=max(errors),
        maximum_norm_drift=max(drift),
        history_rows_per_arm=102,
        reference="Independent NumPy spectral propagation and explicit mode-swap matrix",
    )
