"""Independent repeated-readout reference and strict reproducibility verification."""

import math

import numpy as np

from . import readout
from .echo import compare_tree
from .twomode import sample

ARMS = ("ideal", "finite")
CASES = ("baseline", "more_atoms", "more_shots")
CONVENTION = (
    "v0.14 readout; independent full-scan repetitions; LCG blocks: trial,case,setting,arm; "
    "circular statistics conditional on resolved fits"
)


def draws_per_trial(p):
    return 2 * p["readout"]["points"] * (2 * p["readout"]["shots"] + p["more_shots"])


def validate(plan):
    if set(plan) != {"readout", "more_atoms", "more_shots", "repetitions"}:
        raise ValueError("Unknown precision settings.")
    p = plan | dict(readout=readout.validate(plan["readout"]))
    for k, lo, hi in [
        ("more_atoms", p["readout"]["base"]["atoms"] + 1, 100),
        ("more_shots", p["readout"]["shots"] + 1, 4096),
        ("repetitions", 20, 300),
    ]:
        x = p[k]
        if type(x) not in (int, float) or not math.isfinite(x) or int(x) != x or not lo <= x <= hi:
            raise ValueError(f"Invalid {k}.")
        p[k] = int(x)
    if draws_per_trial(p) * p["repetitions"] > 16000000:
        raise ValueError("Workload exceeds 16 million count draws.")
    return p


def jump(seed, steps):
    # Compose integer affine maps, independently of the browser Math.imul operations.
    a, c, x = 1664525, 1013904223, seed
    while steps:
        if steps & 1:
            x = (a * x + c) % 2**32
        a, c = a * a % 2**32, (a * c + c) % 2**32
        steps //= 2
    return x


def configs(p):
    return [
        dict(
            name=name,
            plan=readout.validate(
                p["readout"]
                | dict(
                    base=p["readout"]["base"]
                    | dict(
                        atoms=p["more_atoms"]
                        if name == "more_atoms"
                        else p["readout"]["base"]["atoms"]
                    ),
                    shots=p["more_shots"] if name == "more_shots" else p["readout"]["shots"],
                )
            ),
        )
        for name in CASES
    ]


def model_case(item):
    name, plan = item["name"], item["plan"]
    source = readout.incoming(plan)
    points = []
    for i in range(plan["points"]):
        r = readout.states(plan, source, i)
        points.append(dict(index=i, alpha=r["alpha"], arms={a: r["arms"][a] for a in ARMS}))
    model_fits = {
        a: readout.fit(
            [
                dict(
                    alpha=r["alpha"],
                    z=2 * r["arms"][a]["mean_left"] / plan["base"]["atoms"] - 1,
                    variance_z_mean=0,
                )
                for r in points
            ]
        )
        for a in ARMS
    }
    b = plan["base"]
    eligible = b["initial"] == "coherent" and b["left_fraction"] == 0.5 and b["interaction_hz"] == 0
    return dict(
        name=name,
        plan=plan,
        source=source,
        points=points,
        model_fits=model_fits,
        ideal_scatter_guide=math.sqrt(3 / (2 * b["atoms"] * plan["points"] * plan["shots"]))
        if eligible
        else None,
    )


def trial(p, models, index):
    seed = jump(p["readout"]["seed"], index * draws_per_trial(p))
    result = dict(index=index, cases={})
    for model in models:
        shots, n = model["plan"]["shots"], model["plan"]["base"]["atoms"]
        values = {a: dict(measurements=[], fit=None) for a in ARMS}
        for r in model["points"]:
            for a in ARMS:
                counts = sample(r["arms"][a], shots, seed)["counts"]
                values[a]["measurements"].append(dict(seed=seed, counts=counts))
                seed = jump(seed, shots)
        for a in ARMS:
            values[a]["fit"] = readout.fit(
                [
                    dict(alpha=model["points"][i]["alpha"], **readout.statistics(m["counts"], n))
                    for i, m in enumerate(values[a]["measurements"])
                ]
            )
        result["cases"][model["name"]] = values
    return result


def wrap(x):
    return float(np.angle(np.exp(1j * x)))


def summary(model, records, arm):
    fits = [r["cases"][model["name"]][arm]["fit"] for r in records]
    valid = [f for f in fits if f["phase"] is not None]
    n, truth = len(valid), model["source"]["phase"]
    model_phase = model["model_fits"][arm]["phase"]
    result = dict(
        attempted=len(fits),
        resolved=n,
        unresolved=len(fits) - n,
        circular_bias=None,
        circular_scatter=None,
        wrapped_rmse=None,
        rms_reported_se=None,
        scatter_over_se=None,
        within_one_se=None,
        model_bias=wrap(model_phase - truth)
        if truth is not None and model_phase is not None
        else None,
    )
    if n < 2:
        return result
    phases = np.array([f["phase"] for f in valid])
    ses = np.array([f["phase_se"] for f in valid])
    mean = np.exp(1j * phases).mean()
    length = min(1, abs(mean))
    if length > 1e-8:
        result["circular_scatter"] = math.sqrt(max(0, -2 * math.log(length)))
        if truth is not None:
            result["circular_bias"] = wrap(float(np.angle(mean)) - truth)
    result["rms_reported_se"] = float(np.sqrt(np.mean(ses**2)))
    if result["rms_reported_se"] > 0 and result["circular_scatter"] is not None:
        result["scatter_over_se"] = result["circular_scatter"] / result["rms_reported_se"]
    if truth is not None:
        errors = np.angle(np.exp(1j * (phases - truth)))
        result["wrapped_rmse"] = float(np.sqrt(np.mean(errors**2)))
        result["within_one_se"] = float(np.mean(abs(errors) <= ses))
    return result


def report(p, models, records, status):
    return dict(
        schema="coldatomlab-precision-v1",
        version="0.15.0",
        convention=CONVENTION,
        plan=p,
        status=status,
        models=models,
        records=records,
        summary={m["name"]: {a: summary(m, records, a) for a in ARMS} for m in models},
    )


def verify_export(data):
    p = validate(data["plan"])
    n = len(data["records"])
    if (
        data["status"] not in ("complete", "cancelled")
        or not 1 <= n <= p["repetitions"]
        or (data["status"] == "complete" and n != p["repetitions"])
    ):
        raise ValueError("Invalid completed repetition prefix.")
    models = [model_case(item) for item in configs(p)]
    records = [trial(p, models, i) for i in range(n)]
    expected = report(p, models, records, data["status"])
    compare_tree(data, expected, "Precision")
    errors, drift = [], []
    for saved, reference in zip(data["models"], models, strict=True):
        ss = [saved["source"]] + [r["arms"][a] for r in saved["points"] for a in ARMS]
        rs = [reference["source"]] + [r["arms"][a] for r in reference["points"] for a in ARMS]
        for x, y in zip(ss, rs, strict=True):
            psi = np.array(x["real"]) + 1j * np.array(x["imag"])
            oracle = np.array(y["real"]) + 1j * np.array(y["imag"])
            errors.append(float(np.linalg.norm(psi - oracle)))
            drift.append(float(abs(np.vdot(psi, psi).real - 1)))
    if max(errors) > 5e-8 or max(drift) > 1e-9:
        raise ValueError("Precision model state or norm tolerance exceeded.")
    return dict(
        verified=True,
        repetitions_verified=n,
        cases_verified=3,
        status=data["status"],
        maximum_complex_state_l2=max(errors),
        maximum_norm_drift=max(drift),
        reference="Independent NumPy propagation, new count draws, fits and circular statistics",
    )
