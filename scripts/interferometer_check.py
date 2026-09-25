"""Hardware WebGPU interferometer checks and independent float64 comparisons."""

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

import numpy as np
from playwright.sync_api import sync_playwright

from coldatomlab.interferometry3d import gaussian_pair, measurements, stages
from coldatomlab.solver3d import Config3D, Solver3D


def cpu_run(c):
    sim = Solver3D(c)
    marks = []
    targets = (
        [stages(c)[0], stages(c)[1] - 1, stages(c)[1], stages(c)[2]]
        if c.experiment == "sequence"
        else [round(c.duration / c.dt)]
    )
    for target in targets:
        while sim.steps < target and not sim.warning and not sim.complete:
            sim.advance(min(20, target - sim.steps))
        assert not sim.warning, sim.warning
        marks.append(
            {
                "diagnostics": sim.diagnostics(),
                "measurement": measurements(
                    c, sim.x, sim.psi, sim.steps, sim.release_step is not None
                ),
            }
        )
    return sim, marks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766")
    parser.add_argument("--refinements", action="store_true")
    args = parser.parse_args()
    out = Path("artifacts/interferometer")
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page()
        page.goto(args.url + "/gpu.html")
        page.wait_for_load_state("networkidle")
        for name, kw in [
            ("pair_zero", dict(experiment="pair", scattering_nm=0, duration=3)),
            ("pair_pi", dict(experiment="pair", scattering_nm=0, duration=3, relative_phase=np.pi)),
            (
                "pair_shift",
                dict(experiment="pair", scattering_nm=0, duration=3, relative_phase=0.7),
            ),
            ("sequence", dict(experiment="sequence", atoms=2000, dt=0.006)),
            ("reverse", dict(experiment="sequence", atoms=2000, dt=0.006, hold_bias=-1)),
        ]:
            c = Config3D(**({"length": 32, **kw} if kw["experiment"] == "pair" else kw))
            start = time.perf_counter()
            result = page.evaluate(
                """async c=>{
              const s=await GPUCloud3D.create(c), marks=[];
              const targets=c.experiment==='sequence' ? [Interferometry3D.stages(c)[0],Interferometry3D.stages(c)[1]-1,Interferometry3D.stages(c)[1],Interferometry3D.stages(c)[2]] : [Math.round(c.duration/c.dt)];
              for(const target of targets){while(s.steps<target&&!s.warning&&!s.complete) await s.advance(Math.min(20,target-s.steps));marks.push({diagnostics:s.diagnostics,measurement:Interferometry3D.measure(s)});}
              const result={export:s.export(),marks,warning:s.warning};s.destroy();return result;
            }""",
                asdict(c),
            )
            assert not result["warning"], result["warning"]
            (out / f"{name}.json").write_text(json.dumps(result["export"]))
            gpu_seconds = time.perf_counter() - start
            sim, marks = cpu_run(c)
            saved = np.asarray(result["export"]["psi_real"]) + 1j * np.asarray(
                result["export"]["psi_imag"]
            )
            error = float(np.linalg.norm((saved - sim.psi).ravel()) * sim.dx**1.5)
            widths = (
                np.asarray(result["marks"][-1]["diagnostics"]["widths"])
                / sim.diagnostics()["widths"]
                - 1
            )
            assert error < 0.005, (name, error)
            assert max(abs(widths)) < 0.005
            entry = {
                "gpu_seconds_including_export": gpu_seconds,
                "field_l2": error,
                "relative_width_errors": widths.tolist(),
                "gpu": result["marks"],
                "cpu": marks,
                "adapter": result["export"]["backend"]["adapter"],
            }
            if c.experiment == "pair":
                exact = gaussian_pair(c, sim.x, sim.time)
                entry["cpu_analytic_l2"] = float(
                    np.linalg.norm((sim.psi - exact).ravel()) * sim.dx**1.5
                )
                entry["gpu_analytic_l2"] = float(
                    np.linalg.norm((saved - exact).ravel()) * sim.dx**1.5
                )
                assert entry["cpu_analytic_l2"] < 1e-4, entry["cpu_analytic_l2"]
            report[name] = entry
            (out / "validation.json").write_text(json.dumps(report, indent=2))
            print(name, error, widths, flush=True)
        browser.close()
    if args.refinements:
        base = report["sequence"]["cpu"][-1]
        for name, kw in [
            # Compare at the same rounded physical end time (5.598), not 5.601.
            ("half_dt", dict(dt=0.003, duration=1.998)),
            ("finer_grid", dict(n=96)),
            ("larger_box", dict(n=96, length=36)),
            ("half_preparation", dict(preparation_dt=0.001)),
        ]:
            c = Config3D(experiment="sequence", atoms=2000, **{**dict(dt=0.006), **kw})
            sim, marks = cpu_run(c)
            diff = (
                np.asarray(sim.diagnostics()["widths"]) / base["diagnostics"]["widths"] - 1
            ).tolist()
            report[name] = {"cpu": marks, "relative_width_change": diff}
            assert max(abs(v) for v in diff) < 0.01, (name, diff)
            (out / "validation.json").write_text(json.dumps(report, indent=2))
            print(name, diff, flush=True)


if __name__ == "__main__":
    main()
