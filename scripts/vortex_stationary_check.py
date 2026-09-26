"""Stationary/full-3D TOF refinement and the paper's explicitly reduced model."""

import argparse
import json
import time
from pathlib import Path

import numpy as np

from coldatomlab.vortex import Vortex
from coldatomlab.vortex_paper import PaperVortex

OUT = Path("artifacts/vortex-sequence")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analyse", action="store_true", help="Inspect the saved refinement run.")
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.analyse:
        analyse(json.loads((OUT / "refinement.json").read_text(encoding="utf8")))
        return
    report = {}
    for name, n, length in [
        ("base", 64, 24),
        ("fine", 128, 24),
        ("large", 128, 32),
        ("small", 64, 16),
        ("small_fine", 128, 16),
    ]:
        started = time.perf_counter()
        s = Vortex(dict(n=n, length=length, stationary=1, g=4 * np.pi * 20, axial_hz=50))
        print(name, "prepared", s.preparation, flush=True)
        np.savez_compressed(OUT / f"{name}-initial.npz", field=s.initial)
        rows = [s.diagnostics()]
        s.release()
        for i in range(10):
            s.advance(50)
            rows.append(s.diagnostics())
            print(name, "tof", (i + 1) * 0.2, rows[-1]["paper_core"], flush=True)
        np.savez_compressed(OUT / f"{name}-final.npz", field=s.psi)
        report[name] = dict(
            config=s.config,
            preparation=s.preparation,
            rows=rows,
            seconds=time.perf_counter() - started,
        )
        (OUT / "refinement.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    c = report["fine"]["config"] | dict(dt=0.002)
    s = Vortex(c, np.load(OUT / "fine-initial.npz")["field"])
    s.release()
    s.advance(1000)
    report["half_dt"] = dict(
        diagnostics=s.diagnostics(),
        l2=float(np.linalg.norm(s.psi - np.load(OUT / "fine-final.npz")["field"]) * s.dx**1.5),
    )
    for n in [256, 512, 1024]:
        for coupling in [0, 20]:
            s = PaperVortex(coupling, cells=n)
            rows = [s.diagnostics()]
            for i in range(10):
                s.advance(100)
                rows.append(s.diagnostics())
            report[f"paper-{coupling}-{n}"] = dict(preparation=s.preparation, rows=rows)
    (OUT / "refinement.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    analyse(report)


def analyse(report):
    """Separate fixed-box grid errors, fixed-spacing box errors and model differences."""

    def ratios(name):
        return np.array([r["paper_core"]["core_ratio"] for r in report[name]["rows"]])

    # L=16 is deliberately a stress test: it becomes unsafe late in the run.
    # Only compare boxes on their common low-boundary interval, t<=1.2.
    result = dict(
        grid_L24_max_ratio_change=float(np.max(abs(ratios("base") - ratios("fine")))),
        grid_L16_max_ratio_change_to_1p2=float(
            np.max(abs(ratios("small")[:7] - ratios("small_fine")[:7]))
        ),
        box_dx025_max_ratio_change_to_1p2=float(
            np.max(abs(ratios("small")[:7] - ratios("large")[:7]))
        ),
        default_vs_finest_initial_ratio_change=float(
            abs(ratios("large")[0] - ratios("small_fine")[0])
        ),
        default_vs_L24_fine_final_ratio_change=float(abs(ratios("large")[-1] - ratios("fine")[-1])),
        half_dt_field_l2=report["half_dt"]["l2"],
        half_dt_final_ratio_change=abs(
            report["half_dt"]["diagnostics"]["paper_core"]["core_ratio"] - ratios("fine")[-1]
        ),
        small_box_final_edge=report["small"]["rows"][-1]["edge_probability"],
        default_max_edge=max(r["edge_probability"] for r in report["large"]["rows"]),
        default_max_norm_drift=max(abs(r["norm"] - 1) for r in report["large"]["rows"]),
    )
    s = Vortex(report["large"]["config"], np.load(OUT / "large-initial.npz")["field"])
    s.release()
    free_energy = s.diagnostics()["energy"]
    result["default_free_energy_drift"] = max(
        abs(r["energy"] - free_energy) for r in report["large"]["rows"][1:]
    )
    for coupling in [0, 20]:
        a = report[f"paper-{coupling}-512"]["rows"]
        b = report[f"paper-{coupling}-1024"]["rows"]
        result[f"paper_{coupling}_max_ratio_refinement"] = max(
            abs(x["core_ratio"] - y["core_ratio"]) for x, y in zip(a, b)
        )
    paper = report["paper-20-1024"]["rows"]
    result["model_difference_initial"] = ratios("small_fine")[0] - paper[0]["core_ratio"]
    result["model_difference_final"] = ratios("large")[-1] - paper[-1]["core_ratio"]
    (OUT / "errors.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    print(json.dumps(result, indent=2), flush=True)
    assert result["half_dt_field_l2"] < 1e-5
    assert result["default_max_norm_drift"] < 1e-9
    assert result["default_max_edge"] < 1e-8
    assert result["default_free_energy_drift"] < 1e-5
    assert result["box_dx025_max_ratio_change_to_1p2"] < 1e-5
    # This is a bounded-resolution comparison, not a sub-percent initial-core claim.
    assert result["default_vs_finest_initial_ratio_change"] < 0.002
    assert result["default_vs_L24_fine_final_ratio_change"] < 1e-4
    assert result["paper_20_max_ratio_refinement"] < 0.0005
    print("Declared norm, energy, boundary, time and observable tolerances passed.", flush=True)


if __name__ == "__main__":
    main()
