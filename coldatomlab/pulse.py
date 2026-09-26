"""Independent matrix/spectral reference for centered finite tunnelling pulses."""

import math

import numpy as np

from . import echo, preparation
from .twomode import diagnostics, hamiltonian, initial_state

ARMS = ("no_echo", "ideal", "short", "nominal", "long")
CONVENTION = (
    "fixed-N; H/h=-J(aL†aR+aR†aL)+U m^2-bias m; equal total time; centered rectangular pulse; "
    "tau_pi=1/(4J) seconds; ideal S global phase omitted, finite pulse phase retained"
)


def ensemble(plan):
    return {k: v for k, v in plan.items() if k not in ("pulse_j_hz", "duration_error")}


def validate(plan):
    p = dict(echo.validate(ensemble(plan)))
    for key, lo, hi in (("pulse_j_hz", 0.5, 20), ("duration_error", 0, 0.5)):
        value = plan[key]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not lo <= value <= hi
        ):
            raise ValueError(f"Invalid {key}.")
        p[key] = value
    if 250 / p["pulse_j_hz"] * (1 + p["duration_error"]) >= p["base"]["duration_ms"]:
        raise ValueError("The longest pulse must be shorter than total duration.")
    return p


def windows(p):
    duration = p["base"]["duration_ms"]
    return {
        arm: dict(
            width_ms=(width := 250 / p["pulse_j_hz"] * ratio),
            ratio=ratio,
            start_ms=(duration - width) / 2,
            end_ms=(duration + width) / 2,
        )
        for arm, ratio in (
            ("short", 1 - p["duration_error"]),
            ("nominal", 1),
            ("long", 1 + p["duration_error"]),
        )
    }


def checkpoints(p):
    events = [p["base"]["duration_ms"] / 2]
    for w in windows(p).values():
        events.extend((w["start_ms"], w["end_ms"]))
    times = []
    pulse_times = [
        w["start_ms"] + w["width_ms"] * i / 20 for w in windows(p).values() for i in range(21)
    ]
    for time in events + pulse_times + [p["base"]["duration_ms"] * i / 100 for i in range(101)]:
        if not any(abs(time - t) < 1e-9 for t in times):
            times.append(time)
    result = []
    for time in sorted(times):
        if any(abs(time - t) < 1e-9 for t in events):
            result.append(dict(time_ms=time, side="before"))
        result.append(dict(time_ms=time, side="after"))
    return result


def evolve(plan, recipe):
    c = recipe["config"]
    if c["tunnelling_hz"] != 0:
        raise ValueError("Hold J must be zero.")
    pc = c | dict(tunnelling_hz=plan["pulse_j_hz"])
    hold_e, hold_v = np.linalg.eigh(hamiltonian(c))
    pulse_e, pulse_v = np.linalg.eigh(hamiltonian(pc))
    psi = initial_state(c)
    total = c["duration_ms"]
    win = windows(plan)

    def propagate(state, time, pulsing=False):
        e, v = (pulse_e, pulse_v) if pulsing else (hold_e, hold_v)
        return v @ (np.exp(-2j * np.pi * e * time / 1000) * (v.T @ state))

    def observe(state, time, pulsing=False):
        return dict(
            time_ms=time,
            real=state.real.tolist(),
            imag=state.imag.tolist(),
            **diagnostics(pc if pulsing else c, state),
        )

    swap = np.eye(c["atoms"] + 1)[::-1]
    swapped = swap @ propagate(psi, total / 2)
    incoming, outgoing, boundaries = {}, {}, {}
    for arm, w in win.items():
        incoming[arm] = propagate(psi, w["start_ms"])
        outgoing[arm] = propagate(incoming[arm], w["width_ms"], True)
        boundaries[arm] = dict(
            before_on=observe(incoming[arm], w["start_ms"]),
            after_on=observe(incoming[arm], w["start_ms"], True),
            before_off=observe(outgoing[arm], w["end_ms"], True),
            after_off=observe(outgoing[arm], w["end_ms"]),
        )
    record = dict(**recipe, arms={arm: dict(history=[]) for arm in ARMS}, boundaries=boundaries)
    for point in checkpoints(plan):
        t, after = point["time_ms"], point["side"] == "after"
        for arm in ARMS:
            stage, active = 0, 0
            if arm == "no_echo":
                state = observe(propagate(psi, t), t)
            elif arm == "ideal":
                applied = t > total / 2 + 1e-9 or (abs(t - total / 2) < 1e-9 and after)
                stage = 2 if applied else 0
                state = observe(
                    propagate(swapped if applied else psi, max(0, t - total / 2) if applied else t),
                    t,
                )
            else:
                w = win[arm]
                if t < w["start_ms"] - 1e-9 or (abs(t - w["start_ms"]) < 1e-9 and not after):
                    state = observe(propagate(psi, t), t)
                elif t > w["end_ms"] + 1e-9 or (abs(t - w["end_ms"]) < 1e-9 and after):
                    stage = 2
                    state = observe(propagate(outgoing[arm], max(0, t - w["end_ms"])), t)
                else:
                    stage, active = 1, plan["pulse_j_hz"]
                    state = observe(
                        propagate(
                            incoming[arm], max(0, min(w["width_ms"], t - w["start_ms"])), True
                        ),
                        t,
                        True,
                    )
            record["arms"][arm]["state"] = state
            record["arms"][arm]["history"].append(
                dict(
                    **{key: state[key] for key in preparation.HISTORY_KEYS},
                    stage=stage,
                    active_j_hz=active,
                )
            )
    ideal_state = record["arms"]["ideal"]["state"]
    target = np.array(ideal_state["real"]) + 1j * np.array(ideal_state["imag"])
    for arm in ARMS:
        state = record["arms"][arm]["state"]
        vector = np.array(state["real"]) + 1j * np.array(state["imag"])
        record["arms"][arm]["fidelity_to_ideal"] = float(abs(np.vdot(target, vector)) ** 2)
    return record


def reference(p):
    return evolve(p, dict(index=-1, phase_offset=0, bias_offset_hz=0, config=p["base"]))


def aggregate(p, ref, records):
    if not records:
        return None
    result = {}
    for arm in ARMS:
        result[arm] = preparation.aggregate(
            ensemble(p), ref["arms"][arm], [r["arms"][arm] for r in records]
        )
        for i, row in enumerate(result[arm]["history"]):
            del row["guide_coherence"]
            for key in ("stage", "active_j_hz"):
                row[key] = ref["arms"][arm]["history"][i][key]
        result[arm]["mean_fidelity_to_ideal"] = float(
            np.mean([r["arms"][arm]["fidelity_to_ideal"] for r in records])
        )
    return result


def verify_export(data):
    if data.get("schema") != "coldatomlab-pulse-v1" or data.get("convention") != CONVENTION:
        raise ValueError("Unknown pulse convention.")
    p = validate(data["plan"])
    count = len(data["records"])
    if data["status"] not in ("complete", "cancelled") or not 1 <= count <= p["preparations"]:
        raise ValueError("Invalid completed-prefix status.")
    if data["status"] == "complete" and count != p["preparations"]:
        raise ValueError("Incomplete comparison marked complete.")
    ref = reference(p)
    records = [evolve(p, r) for r in preparation.recipes(ensemble(p))[:count]]
    for key, expected in dict(
        windows=windows(p),
        checkpoints=checkpoints(p),
        reference=ref,
        records=records,
        aggregate=aggregate(p, ref, records),
    ).items():
        echo.compare_tree(data[key], expected, key)
    errors, drift = [], []
    for saved, expected in zip([data["reference"], *data["records"]], [ref, *records], strict=True):
        pairs = [(saved["arms"][arm]["state"], expected["arms"][arm]["state"]) for arm in ARMS]
        for arm in windows(p):
            pairs.extend(
                (saved["boundaries"][arm][edge], expected["boundaries"][arm][edge])
                for edge in saved["boundaries"][arm]
            )
        for a, b in pairs:
            v = np.array(a["real"]) + 1j * np.array(a["imag"])
            w = np.array(b["real"]) + 1j * np.array(b["imag"])
            errors.append(float(np.linalg.norm(v - w)))
            drift.append(abs(a["norm"] - 1))
        for arm in ARMS:
            drift.extend(abs(r["norm"] - 1) for r in saved["arms"][arm]["history"])
    if max(errors) > 5e-8 or max(drift) > 1e-9:
        raise ValueError("Finite pulse state or norm tolerance exceeded.")
    return dict(
        verified=True,
        preparations_verified=count,
        status=data["status"],
        maximum_complex_state_l2=max(errors),
        maximum_norm_drift=max(drift),
        history_rows_per_arm=len(data["checkpoints"]),
        reference="Independent NumPy eigensystems for holds and finite pulses, with full complex-state checks",
    )
