"""Hardware stirred evolution, independent CPU replay and existing-GPU regression."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve


def main():
    out = Path("artifacts/vortex")
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with serve() as url, sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page()
        page.goto(url + "/#vortex", wait_until="networkidle")
        frame = page.frame(url=url + "/vortex.html#embedded")
        frame.wait_for_function('typeof VortexGPU !== "undefined"')
        first = frame.evaluate(
            """async()=>{window.probe=await VortexGPU.create({g:300,charge:0,height:12,stir_time:4,duration:5});return probe.history[0]}"""
        )
        assert first["winding"] == 0 and first["positive"] == first["negative"] == 0
        for i in range(5):
            d = frame.evaluate(
                """async()=>{for(let k=0;k<12;k++)await probe.advance(20);await probe.advance(10);return probe.history.at(-1)}"""
            )
            print("stir", i + 1, d, flush=True)
        data = frame.evaluate("probe.export()")
        frame.evaluate("probe.destroy()")
        assert data["steps"] == 1250 and not data["warning"] and data["history"][-1]["winding"] == 2
        assert data["history"][-1]["positive"] > 0 and not data["backend"]["fallback"]
        (out / "stir.json").write_text(json.dumps(data), encoding="utf8")
        report["stir"] = verify_export(data)
        (out / "stir-replay.json").write_text(json.dumps(report["stir"], indent=2), encoding="utf8")
        # Same shared shader hook must preserve the earlier lab's protocols.
        page.goto(url + "/#lab3d")
        page.wait_for_function('typeof GPUCloud3D !== "undefined"')
        for kind in ["single", "sequence"]:
            data = page.evaluate(
                """async kind=>{const s=await GPUCloud3D.create({experiment:kind,n:32,length:16,atoms:2000,reference_hz:50,fx_hz:50,fy_hz:50,fz_hz:100,preparation_dt:.002,scattering_nm:0,dt:.004,duration:.1,barrier_width:1,split_time:.1,hold_time:.1});if(kind==='single')await s.release();for(let i=0;i<12&&!s.complete&&!s.warning;i++)await s.advance(20);const out=s.export();s.destroy();return out}""",
                kind,
            )
            report[kind] = verify_export(data)
        browser.close()
    (out / "gpu.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print("Hardware vortex and previous GPU protocols verified.")


if __name__ == "__main__":
    main()
