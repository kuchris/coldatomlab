"""Reproducible 3D refinement and TF comparisons; output is ignored by Git."""

import json
import platform
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np

from coldatomlab.solver3d import Config3D, Solver3D, tf_reference


def run(name, **kwargs):
    started = time.perf_counter()
    c = Config3D(**kwargs)
    s = Solver3D(c)
    initial = s.diagnostics()
    s.release()
    e0 = s.diagnostics()["energy"]
    while not s.complete and not s.warning:
        s.advance(20)
    final = s.diagnostics()
    tf = tf_reference(c, [0, s.time])
    result = {
        "name": name,
        "config": asdict(c),
        "preparation": s.preparation,
        "initial": initial,
        "final": final,
        "warning": s.warning,
        "wall_seconds": time.perf_counter() - started,
        "relative_energy_change": (final["energy"] - e0) / e0,
        "norm_drift": final["norm"] - 1,
        "history": s.history,
        "tf": tf,
    }
    if tf:
        result["tf_relative_width_error"] = (
            np.array(final["widths"]) / tf["widths"][-1] - 1
        ).tolist()
        result["initial_kinetic_interaction_ratio"] = (
            initial["kinetic"] / initial["interaction_energy"]
        )
    else:
        exact = np.sqrt((1 + c.omegas**2 * s.time**2) / (2 * c.omegas))
        result["gaussian_relative_width_error"] = (np.array(final["widths"]) / exact - 1).tolist()
    print(
        name,
        json.dumps({k: v for k, v in result.items() if k not in ("history", "tf", "config")}),
        flush=True,
    )
    return result


def summarize(report):
    cases = {case["name"]: case for case in report["cases"]}
    report["refinement_relative_changes"] = {}
    for baseline, names in (
        ("interacting", ("half_dt", "fine_grid", "large_box", "half_preparation_dt")),
        ("tf", ("tf_half_dt", "tf_fine_grid", "tf_large_box")),
    ):
        ref = cases[baseline]["final"]
        old = [*ref["widths"], ref["aspect_xz"], ref["aspect_yz"]]
        for name in names:
            current = cases[name]["final"]
            assert current["time"] == ref["time"], "Compare equal evolution times."
            values = [*current["widths"], current["aspect_xz"], current["aspect_yz"]]
            report["refinement_relative_changes"][name] = (np.array(values) / old - 1).tolist()
    changes = report["refinement_relative_changes"]
    report["checks"] = {
        "gaussian_rms_below_0.1_percent": max(
            abs(np.array(cases["gaussian"]["gaussian_relative_width_error"]))
        )
        < 1e-3,
        "norm_drift_below_1e-10": all(abs(case["norm_drift"]) < 1e-10 for case in cases.values()),
        "refinement_below_0.5_percent": all(
            max(abs(np.array(v))) < 0.005 for v in changes.values()
        ),
        "full_duration_cases_avoid_boundary": all(
            not c["warning"] for name, c in cases.items() if name != "tf_finer_spacing"
        ),
        "small_tf_box_stops": bool(cases["tf_finer_spacing"]["warning"]),
        "energy_error_decreases_with_dt": all(
            abs(cases[half]["relative_energy_change"])
            < abs(cases[base]["relative_energy_change"]) / 3.8
            for base, half in (("interacting", "half_dt"), ("tf", "tf_half_dt"))
        ),
    }
    report["checks"] = {k: bool(v) for k, v in report["checks"].items()}
    return report


def main():
    out = Path("artifacts/3d-validation.json")
    out.parent.mkdir(exist_ok=True)
    cases = [("gaussian", dict(n=48, length=24, scattering_nm=0, duration=2))]
    base = dict(n=48, length=24, atoms=20000, duration=1.5)
    cases += [
        ("interacting", base),
        ("half_dt", dict(base, dt=0.002)),
        ("fine_grid", dict(base, n=64)),
        ("large_box", dict(base, n=64, length=32)),
        ("half_preparation_dt", dict(base, preparation_dt=0.001)),
    ]
    strong = dict(n=96, length=48, atoms=150000, duration=3)
    cases += [
        ("tf", strong),
        ("tf_finer_spacing", dict(strong, length=40)),
        ("tf_half_dt", dict(strong, dt=0.002)),
        ("tf_fine_grid", dict(strong, n=128)),
        ("tf_large_box", dict(strong, n=128, length=64)),
    ]
    report = {"platform": platform.platform(), "cases": []}
    for name, config in cases:
        report["cases"].append(run(name, **config))
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    summarize(report)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if not all(report["checks"].values()):
        raise SystemExit("3D validation targets failed; inspect the saved report.")


if __name__ == "__main__":
    main()
