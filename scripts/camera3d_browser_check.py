"""Actual 3D camera controls, static-compatible acquisition and source invariance."""

import argparse
import json
import time
from pathlib import Path

import numpy as np
from playwright.sync_api import expect, sync_playwright

from coldatomlab.camera3d import verify_camera
from coldatomlab.replay import verify_export


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/gpu.html")
    parser.add_argument("--cpu", action="store_true")
    args = parser.parse_args()
    out = Path("artifacts/camera3d")
    out.mkdir(parents=True, exist_ok=True)
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport={"width": 1500, "height": 1000}, accept_downloads=True)
        errors, api = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: api.append(r.url) if "/api" in r.url else None)
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        blind = []
        for phase in (0, 0.7, -1.2, 3.0):
            x = np.linspace(-12, 12, 97)
            y = np.exp(-x * x / 72) * (1 + 0.65 * np.cos(2 * np.pi * x / 5 - phase))
            fit = page.evaluate(
                "v=>AbsorptionCamera3D.fit(v.x,v.y)", dict(x=x.tolist(), y=y.tolist())
            )
            assert fit["available"] and abs(fit["phase"] - phase) < 0.01
            assert abs(fit["spacing"] / 5 - 1) < 0.01
            assert abs(fit["contrast"] - 0.65) < 0.02
            blind.append(dict(input_phase=phase, fit=fit))
        report["blind_synthetic"] = blind

        def export(button, name):
            with page.expect_download() as dl:
                page.locator(button).click()
            path = out / f"{name}.json"
            dl.value.save_as(path)
            return json.loads(path.read_text())

        def capture(name):
            start = time.perf_counter()
            page.locator("#camera3d-capture").click()
            expect(page.locator("#camera3d-status")).to_contain_text("Captured at", timeout=30000)
            expect(page.locator("#camera3d-capture")).to_be_enabled()
            expect(page.locator("#camera3d-error")).to_be_hidden()
            record = export("#camera3d-export", name)
            image = record.get("current", record)
            report[name] = dict(
                seconds=time.perf_counter() - start,
                fit=image["image"]["measured"],
                replay=verify_camera(image),
            )
            return record

        # Variable fields may expand below these selectors but never move them.
        positions = []
        for mode in ("single", "pair", "sequence"):
            page.locator("#three-experiment").select_option(mode)
            positions.append(
                page.evaluate("""()=>['experiment','engine','preset'].map(k=>{
                const r=document.getElementById('three-'+k).getBoundingClientRect();
                return [r.x+scrollX,r.y+scrollY];})""")
            )
        assert np.allclose(positions, positions[0]), positions
        report["selector_positions"] = positions
        if args.cpu:
            page.locator("#three-engine").select_option("cpu")
        page.locator("#three-preset").select_option("camera")
        page.locator("#three-load").click()
        if args.cpu:
            page.get_by_text("3D numerical resolution", exact=True).click()
            page.locator("#three-n").select_option("32")
            page.locator("#three-length").select_option("16")
            page.locator("#three-duration").fill("0.1")
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=60000)
        page.locator("#three-run").click()
        if not args.cpu:
            expect(page.locator("#camera3d-capture")).to_be_disabled()
        expect(page.locator("#three-status")).to_have_text("Complete", timeout=60000)
        before = export("#three-export", "source-before")
        ideal = capture("cpu-ideal" if args.cpu else "ideal")
        if args.cpu:
            report["source_replay"] = verify_export(ideal)
        else:
            assert abs(ideal["image"]["measured"]["phase"] - 0.7) < 0.03
            page.locator("#camera3d-pin").click()
            page.locator("#camera3d-fwhm_um").fill("4")
            expect(page.locator("#camera3d-status")).to_contain_text("settings pending")
            comparison = capture("comparison")
            assert comparison["reference"] == ideal
            assert (
                comparison["current"]["image"]["measured"]["contrast"]
                < ideal["image"]["measured"]["contrast"]
            )
            page.locator("#camera3d-panel").screenshot(path=str(out / "desktop.png"))
            page.locator("#camera3d-clear").click()
            page.locator("#camera3d-fwhm_um").fill("8")
            assert not capture("blur8")["image"]["measured"]["available"]
            page.locator("#camera3d-ideal").click()
            for axis in ("y", "x"):
                page.locator("#camera3d-axis").select_option(axis)
                image = capture(f"axis-{axis}")["image"]
                assert image["axes"] == (["x", "z"] if axis == "y" else ["y", "z"])
                assert image["measured"]["available"] == (axis == "y")
            page.locator("#camera3d-axis").select_option("z")
            page.locator("#camera3d-noise").check()
            first = capture("noise")
            again = capture("noise-repeat")
            assert first["image"] == again["image"]
            page.locator("#camera3d-seed").fill("18")
            different = capture("noise-other")
            assert first["image"]["atoms_frame"] != different["image"]["atoms_frame"]
            page.locator("#camera3d-ideal").click()
            page.locator("#camera3d-binning").select_option("2")
            assert not capture("binned")["image"]["measured"]["available"]
            page.locator("#camera3d-fwhm_um").fill("-1")
            page.locator("#camera3d-capture").click()
            expect(page.locator("#camera3d-error")).to_be_visible()
            expect(page.locator("#camera3d-capture")).to_be_enabled()
            page.locator("#camera3d-ideal").click()
            capture("recovered")
            page.get_by_text(
                "Detected light · raw atom / reference / dark frames", exact=True
            ).click()
            for width in (390, 320):
                page.set_viewport_size({"width": width, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
                page.locator("#camera3d-panel").screenshot(path=str(out / f"mobile-{width}.png"))
            report["source_replay"] = verify_export(ideal)

        after = export("#three-export", "source-after")
        assert before == after, "Acquisition changed the solver state."
        page.locator("#three-reset").click()
        expect(page.locator("#three-status")).to_have_text("Ready")
        expect(page.locator("#camera3d-status")).to_contain_text("Source changed")
        assert not errors, errors
        if "gpu.html" in args.url:
            assert not api, api
        report.update(errors=errors, api_requests=api, source_unchanged=True)
        name = "cpu-browser" if args.cpu else "browser"
        (out / f"{name}.json").write_text(json.dumps(report, indent=2), encoding="utf8")
        browser.close()
    print(f"Camera browser checks passed: {out / name}.json")


if __name__ == "__main__":
    main()
