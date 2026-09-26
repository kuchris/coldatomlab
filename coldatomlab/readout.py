"""Independent NumPy reference for spatial two-mode Ramsey-style count readout."""

import math

import numpy as np

from .echo import compare_tree
from .twomode import diagnostics, hamiltonian, initial_state, sample
from .twomode import validate as validate_base

CONVENTION = (
    "fixed-N spatial modes; phase gate exp[-i(N-n)(alpha+pi/2)]; positive-J mixing; "
    "z=Re(q exp[-i alpha]); finite width=(1+error)/(8J) seconds"
)
ARMS = ("direct", "ideal", "finite")


def validate(plan):
    keys = {"base", "hold_ms", "echo", "pulse_j_hz", "duration_error", "points", "shots", "seed"}
    if set(plan) != keys or type(plan["echo"]) is not bool:
        raise ValueError("Unknown readout settings.")
    p = plan | {"base": validate_base(plan["base"])}
    if p["base"]["tunnelling_hz"] != 0:
        raise ValueError("Hold J must be zero.")
    for k, lo, hi, integer in [
        ("hold_ms", 0, 1000, False),
        ("pulse_j_hz", 0.5, 20, False),
        ("duration_error", -0.5, 0.5, False),
        ("points", 8, 32, True),
        ("shots", 16, 4096, True),
        ("seed", 0, 2**32 - 1, True),
    ]:
        x = p[k]
        if (
            type(x) not in (int, float)
            or not math.isfinite(x)
            or not lo <= x <= hi
            or (integer and int(x) != x)
        ):
            raise ValueError(f"Invalid {k}.")
        if integer:
            p[k] = int(x)
    return p


def width(p):
    return 125 / p["pulse_j_hz"] * (1 + p["duration_error"])


def advance(c, psi, ms):
    e, v = np.linalg.eigh(hamiltonian(c))
    return v @ (np.exp(-2j * np.pi * e * ms / 1000) * (v.T @ psi))


def observe(c, psi, time):
    return dict(time_ms=time, real=psi.real.tolist(), imag=psi.imag.tolist(), **diagnostics(c, psi))


def incoming(p):
    c = p["base"]
    psi = initial_state(c)
    if p["echo"]:
        psi = advance(c, advance(c, psi, p["hold_ms"] / 2)[::-1], p["hold_ms"] / 2)
    else:
        psi = advance(c, psi, p["hold_ms"])
    return observe(c, psi, p["hold_ms"])


def statistics(counts, n):
    counts = np.asarray(counts)
    k = np.arange(n + 1)
    shots = int(counts.sum())
    mean = float(k @ counts / shots)
    variance = float((k - mean) ** 2 @ counts / (shots - 1))
    return dict(
        mean_left=mean,
        variance_left=variance,
        sem_left=math.sqrt(variance / shots),
        z=2 * mean / n - 1,
        variance_z_mean=4 * variance / (n * n * shots),
    )


def fit(rows):
    alpha = np.array([r["alpha"] for r in rows])
    z = np.array([r["z"] for r in rows])
    variance = np.array([r["variance_z_mean"] for r in rows])
    design = np.array([np.ones(len(rows)), np.cos(alpha), np.sin(alpha)]).T
    # General linear least squares, independent of the browser Fourier implementation.
    inverse = np.linalg.pinv(design)
    beta = inverse @ z
    cov = (inverse * variance) @ inverse.T
    offset, a, b = beta
    contrast = float(np.hypot(a, b))
    max_var = float(np.linalg.eigvalsh(cov[1:, 1:])[-1])
    resolved = contrast > max(1e-8, 3 * math.sqrt(max(0, max_var)))
    gradient = np.array([-b, a])
    se = (
        math.sqrt(max(0, float(gradient @ cov[1:, 1:] @ gradient))) / contrast**2
        if resolved
        else None
    )
    return dict(
        offset=float(offset),
        cosine=float(a),
        sine=float(b),
        contrast=contrast,
        phase=float(np.arctan2(b, a)) if resolved else None,
        phase_se=se,
        residual_rms=float(np.sqrt(np.mean((z - design @ beta) ** 2))),
        covariance=cov.tolist(),
        resolved=resolved,
    )


def states(p, source, index):
    n = p["base"]["atoms"]
    alpha = 2 * math.pi * index / p["points"]
    psi = np.asarray(source["real"]) + 1j * np.asarray(source["imag"])
    shifted = psi * np.exp(-1j * (n - np.arange(n + 1)) * (alpha + math.pi / 2))
    result = dict(index=index, alpha=alpha, arms={})
    for arm in ARMS:
        c = p["base"] | dict(tunnelling_hz=p["pulse_j_hz"], duration_ms=1000)
        ideal = arm == "ideal"
        if ideal:
            c |= dict(interaction_hz=0, bias_hz=0)
        if arm == "direct":
            state = source
        else:
            duration = 125 / p["pulse_j_hz"] if ideal else width(p)
            state = observe(
                c, advance(c, shifted, duration), p["hold_ms"] + (0 if ideal else width(p))
            )
        result["arms"][arm] = state
    return result


def point(p, source, index):
    values = states(p, source, index)
    n = p["base"]["atoms"]
    result = dict(index=index, alpha=values["alpha"], arms={})
    for ai, arm in enumerate(ARMS):
        state = values["arms"][arm]
        seed = p["seed"]
        for _ in range((index * 3 + ai) * p["shots"]):
            seed = (1664525 * seed + 1013904223) % 2**32
        measurement = sample(state, p["shots"], seed)
        result["arms"][arm] = dict(
            state=state, measurement=measurement, statistics=statistics(measurement["counts"], n)
        )
    return result


def report(p, source, records, status):
    fits = None
    if len(records) == p["points"]:
        fits = {}
        for arm in ("ideal", "finite"):
            fits[arm] = dict(
                measured=fit(
                    [dict(alpha=r["alpha"], **r["arms"][arm]["statistics"]) for r in records]
                ),
                model=fit(
                    [
                        dict(
                            alpha=r["alpha"],
                            z=2 * r["arms"][arm]["state"]["mean_left"] / p["base"]["atoms"] - 1,
                            variance_z_mean=0,
                        )
                        for r in records
                    ]
                ),
            )
    return dict(
        schema="coldatomlab-readout-v1",
        version="0.15.0",
        convention=CONVENTION,
        plan=p,
        status=status,
        finite_width_ms=width(p),
        source=source,
        records=records,
        fits=fits,
    )


def verify_export(data):
    p = validate(data["plan"])
    count = len(data["records"])
    if (
        data["status"] not in ("complete", "cancelled")
        or not 1 <= count <= p["points"]
        or (data["status"] == "complete" and count != p["points"])
    ):
        raise ValueError("Invalid completed scan prefix.")
    source = incoming(p)
    records = [point(p, source, i) for i in range(count)]
    expected = report(p, source, records, data["status"])
    if data.get("version") not in ("0.14.0", "0.15.0"):
        raise ValueError("Unknown readout version.")
    expected["version"] = data["version"]
    compare_tree(data, expected, "Readout")
    errors, drift = [], []
    saved_states = [data["source"]] + [r["arms"][a]["state"] for r in data["records"] for a in ARMS]
    expected_states = [source] + [r["arms"][a]["state"] for r in records for a in ARMS]
    for saved, ref in zip(saved_states, expected_states, strict=True):
        psi = np.array(saved["real"]) + 1j * np.array(saved["imag"])
        oracle = np.array(ref["real"]) + 1j * np.array(ref["imag"])
        errors.append(float(np.linalg.norm(psi - oracle)))
        drift.append(float(abs(np.vdot(psi, psi).real - 1)))
    if max(errors) > 5e-8 or max(drift) > 1e-9:
        raise ValueError("Readout field or norm tolerance exceeded.")
    return dict(
        verified=True,
        settings_verified=count,
        status=data["status"],
        maximum_complex_state_l2=max(errors),
        maximum_norm_drift=max(drift),
        reference="Independent NumPy spectral propagation, counting and least-squares fit",
    )
