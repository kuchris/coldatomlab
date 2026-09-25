"""Hardware WebGPU numerical/UI validation. Uses installed Chrome, not software GPU."""

import argparse
import json
from pathlib import Path

import numpy as np
from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    out = Path("artifacts/webgpu")
    out.mkdir(exist_ok=True)
    report = {"numerical": {}, "browser": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
        errors = []
        api = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: api.append(r.url) if "/api" in r.url else None)
        page.goto(args.url + "/gpu.html")
        page.wait_for_load_state("networkidle")
        config = dict(
            n=32,
            length=16,
            dt=0.004,
            atoms=2000,
            scattering_nm=0,
            reference_hz=30,
            fx_hz=30,
            fy_hz=42,
            fz_hz=21,
            duration=0.5,
            preparation_dt=0.002,
        )
        result = page.evaluate(
            """async c=>{window.probe=await GPUCloud3D.create(c);return probe.adapter;}""", config
        )
        assert not result["fallback"] and result["vendor"], result
        report["adapter"] = result
        # Independent random complex FFT oracle tests all axes, not just a Gaussian.
        random = np.random.default_rng(17).normal(size=(32, 32, 32, 2)).astype("float32")
        output = page.evaluate(
            """async data=>{
          probe.device.queue.writeBuffer(probe.fields[0],0,new Float32Array(data));
          const e=probe.device.createCommandEncoder();probe.index=probe.fft(e,probe.fields,0);probe.device.queue.submit([e.finish()]);
          const result=Array.from(await probe.readField());
          const inverse=probe.device.createCommandEncoder();probe.index=probe.fft(inverse,probe.fields,probe.index,true);probe.device.queue.submit([inverse.finish()]);
          return {forward:result,roundtrip:Array.from(await probe.readField())};
        }""",
            random.ravel().tolist(),
        )
        oracle = random[..., 0] + 1j * random[..., 1]

        def complex_field(values, n=32):
            a = np.asarray(values)
            return (a[::2] + 1j * a[1::2]).reshape(n, n, n)

        ref = np.fft.fftn(oracle)
        fft_error = float(
            np.linalg.norm(complex_field(output["forward"]) - ref) / np.linalg.norm(ref)
        )
        roundtrip = float(np.max(abs(complex_field(output["roundtrip"]) - oracle)))
        assert fft_error < 2e-6 and roundtrip < 3e-6
        report["fft"] = {"relative_l2": fft_error, "roundtrip_max": roundtrip}
        await_destroy = "probe.destroy();"
        page.evaluate(await_destroy)
        for name, settings in (
            ("gaussian", dict(config, n=64, length=24, duration=2)),
            (
                "interacting",
                dict(config, n=64, length=24, atoms=20000, scattering_nm=5.3, duration=2),
            ),
            (
                "half_dt",
                dict(config, n=64, length=24, atoms=20000, scattering_nm=5.3, duration=2, dt=0.002),
            ),
            (
                "half_preparation_dt",
                dict(
                    config,
                    n=64,
                    length=24,
                    atoms=20000,
                    scattering_nm=5.3,
                    duration=2,
                    preparation_dt=0.001,
                ),
            ),
            ("tf", dict(config, n=128, length=48, atoms=150000, scattering_nm=5.3, duration=3)),
        ):
            result = page.evaluate(
                """async c=>{
              const start=performance.now();window.probe=await GPUCloud3D.create(c);const initial=probe.diagnostics;
              const prepWall=(performance.now()-start)/1000;await probe.release();const e0=probe.diagnostics.energy;const evolve=performance.now();
              while(!probe.complete&&!probe.warning)await probe.advance(20);
              return {initial,final:probe.diagnostics,preparation:probe.preparation,preparation_wall:prepWall,evolution_wall:(performance.now()-evolve)/1000,relative_energy_drift:probe.diagnostics.energy/e0-1,warning:probe.warning,config:c};
            }""",
                settings,
            )
            assert not result["warning"], result
            assert abs(result["final"]["norm"] - 1) < 0.001
            report["numerical"][name] = result
            if name == "gaussian":
                w = np.array([1, 1.4, 0.7])
                exact = np.sqrt((1 + w * w * 4) / (2 * w))
                err = (np.array(result["final"]["widths"]) / exact - 1).tolist()
                assert max(abs(v) for v in err) < 0.001
                result["relative_analytic_width_errors"] = err
            if name in ("gaussian", "interacting"):
                exported = page.evaluate("probe.export()")
                (out / f"{name}-export.json").write_text(json.dumps(exported))
            page.evaluate("probe.destroy()")
            print(name, json.dumps(result), flush=True)
            (out / "validation.json").write_text(json.dumps(report, indent=2))
        base = np.array(report["numerical"]["interacting"]["final"]["widths"])
        for name in ("half_dt", "half_preparation_dt"):
            error = np.array(report["numerical"][name]["final"]["widths"]) / base - 1
            assert max(abs(error)) < 0.005
            report["numerical"][name]["relative_width_change"] = error.tolist()
        stopped = page.evaluate(
            """async c=>{
          window.probe=await GPUCloud3D.create(c);
          const shifted=new Float32Array(probe.initial.length),n=probe.n;
          for(let x=0;x<n;x++)for(let y=0;y<n;y++)for(let z=0;z<n;z++){
            const i=((x*n+y)*n+z)*2,j=((((x+14)%n)*n+y)*n+z)*2;
            shifted[j]=probe.initial[i];shifted[j+1]=probe.initial[i+1];
          }
          probe.device.queue.writeBuffer(probe.fields[probe.index],0,shifted);
          await probe.release();await probe.advance(20);
          const stopped={steps:probe.steps,warning:probe.warning};await probe.reset();
          probe.destroy();await new Promise(r=>setTimeout(r,10));
          try{await probe.advance(1);stopped.device_loss=false;}catch{stopped.device_loss=true;}
          return stopped;
        }""",
            config,
        )
        assert stopped["steps"] == 1 and "boundary" in stopped["warning"] and stopped["device_loss"]
        report["boundary_and_device_loss"] = stopped
        # End-to-end controls on the static entry point: no simulation API.
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#three-engine-note")).to_contain_text("float32")
        canvas = page.locator("#three-surface")
        pixels = canvas.screenshot()
        canvas.focus()
        page.keyboard.press("ArrowRight")
        assert pixels != canvas.screenshot()
        page.locator("#three-release").click()
        page.locator("#three-step").click()
        expect(page.locator("#three-status")).to_have_text("Paused")
        page.locator("#three-run").click()
        page.wait_for_timeout(200)
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Paused")
        frozen = page.locator("#three-time").inner_text()
        page.wait_for_timeout(300)
        assert page.locator("#three-time").inner_text() == frozen
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Complete", timeout=60000)
        page.locator("#three-columns").click()
        expect(page.locator("#three-image-note")).to_contain_text("atoms / µm²")
        with page.expect_download() as download:
            page.locator("#three-export").click()
        download.value.save_as(out / "browser-export.json")
        page.locator("#three-form .numerics summary").click()
        page.locator("#three-n").select_option("96")
        page.locator("#three-prepare").click()
        expect(page.locator("#three-error")).to_contain_text("32³, 64³ or 128³")
        page.locator("#three-reset").click()
        expect(page.locator("#three-status")).to_have_text("Ready")
        expect(page.locator("#three-n")).to_have_value("64")
        page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
        page.screenshot(path=str(out / "desktop.png"), full_page=True)
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(out / f"mobile-{width}.png"), full_page=True)
        assert not errors, errors
        assert not api, api
        # Missing hardware is an explicit error, with no silent CPU calculation.
        unavailable = browser.new_page()
        unavailable.add_init_script("Object.defineProperty(navigator,'gpu',{value:undefined})")
        unavailable.goto(args.url + "/gpu.html")
        unavailable.locator("#three-prepare").click()
        expect(unavailable.locator("#three-error")).to_contain_text("WebGPU is unavailable")
        report["browser"] = {
            "no_simulation_api": not api,
            "page_errors": errors,
            "pause_reset_export_views_mobile": True,
            "unsupported_hardware_error": True,
        }
        (out / "validation.json").write_text(json.dumps(report, indent=2))
        browser.close()
    print("Hardware WebGPU checks passed.")


if __name__ == "__main__":
    main()
