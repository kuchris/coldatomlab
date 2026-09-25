"""Exercise 3D interferometer controls and comparison export in hardware Chrome."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/gpu.html")
    parser.add_argument("--cpu-smoke", action="store_true")
    args = parser.parse_args()
    out = Path("artifacts/interferometer")
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
        assert page.locator("#three-experiment").input_value() == "single"
        report["presets"] = page.locator("#three-preset").inner_text()
        if args.cpu_smoke:
            page.locator("#three-engine").select_option("cpu")
            page.locator("#three-preset").select_option("sequence")
            page.locator("#three-load").click()
            page.get_by_text("3D numerical resolution", exact=True).click()
            page.locator("#three-n").select_option("32")
            page.locator("#three-length").select_option("16")
            for key, value in {
                "atoms": "100",
                "dt": "0.01",
                "barrier_width": "1",
                "split_time": "0.2",
                "hold_time": "0.1",
                "duration": "0.1",
            }.items():
                page.locator(f"#three-{key}").fill(value)
            page.locator("#three-prepare").click()
            expect(page.locator("#three-status")).to_have_text("Ready", timeout=120000)
            expect(page.locator("#three-release")).to_be_disabled()
            page.locator("#three-run").click()
            expect(page.locator("#three-status")).to_have_text("Complete", timeout=120000)
            expect(page.locator("#three-timeline")).to_contain_text("Complete")
            expect(page.locator("#three-engine-note")).to_contain_text("float64")
            with page.expect_download() as dl:
                page.locator("#three-export").click()
            dl.value.save_as(out / "cpu-sequence-ui.json")
            from coldatomlab.replay import verify_export

            result = verify_export(json.loads((out / "cpu-sequence-ui.json").read_text()))
            assert result["replayed"]
            assert not errors, errors
            (out / "cpu-browser.json").write_text(json.dumps(result, indent=2))
            browser.close()
            print("CPU sequence browser and exact replay passed.")
            return

        def load(name):
            page.locator("#three-preset").select_option(name)
            page.locator("#three-load").click()
            page.locator("#three-prepare").click()
            expect(page.locator("#three-status")).to_have_text("Ready", timeout=120000)
            expect(page.locator("#three-error")).to_be_hidden()

        def run():
            page.locator("#three-run").click()
            expect(page.locator("#three-status")).to_have_text("Complete", timeout=120000)
            expect(page.locator("#three-warning")).to_be_hidden()

        load("pair")
        expect(page.locator("#three-release")).to_be_disabled()
        run()
        report["zero"] = page.locator("#three-interference-values").inner_text()
        page.locator("#three-pin").click()
        expect(page.locator("#three-clear-pin")).to_be_enabled()
        pinned = page.locator("#three-pin-note").inner_text().split("Current")[0]
        load("opposite")
        run()
        assert page.locator("#three-pin-note").inner_text().startswith(pinned)
        report["pi"] = page.locator("#three-interference-values").inner_text()
        with page.expect_download() as dl:
            page.locator("#three-export-pair").click()
        dl.value.save_as(out / "comparison.json")
        data = json.loads((out / "comparison.json").read_text())
        assert data["schema"] == "coldatomlab-3d-comparison-v1"
        assert data["reference"]["config"]["relative_phase"] == 0
        assert data["current"]["config"]["relative_phase"] > 3.14
        page.locator("#three-interferometer").screenshot(path=str(out / "pair-comparison.png"))
        # Invalid analytic-pair preparation must preserve the previous experiment.
        page.locator("#three-scattering_nm").fill("5.3")
        page.locator("#three-prepare").click()
        expect(page.locator("#three-error")).to_contain_text("zero scattering")
        page.locator("#three-reset").click()
        expect(page.locator("#three-status")).to_have_text("Ready")
        assert page.locator("#three-scattering_nm").input_value() == "0"
        load("sequence")
        expect(page.locator("#three-timeline")).to_contain_text("Split")
        page.locator("#three-step").click()
        expect(page.locator("#three-status")).to_have_text("Paused")
        assert float(page.locator("#three-time").inner_text()) > 0
        page.locator("#three-run").click()
        expect(page.locator("#three-run")).to_contain_text("Pause")
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Paused")
        held = page.locator("#three-time").inner_text()
        page.wait_for_timeout(300)
        assert page.locator("#three-time").inner_text() == held
        run()
        expect(page.locator("#three-timeline")).to_contain_text("Complete")
        expect(page.locator("#three-trap")).to_have_text("All axes released")
        report["sequence"] = page.locator("#three-interference-values").inner_text()
        for view in ("columns", "slices"):
            page.locator(f"#three-{view}").click()
            expect(page.locator(f"#three-{view}")).to_have_attribute("aria-pressed", "true")
        with page.expect_download() as dl:
            page.locator("#three-export").click()
        dl.value.save_as(out / "sequence-ui.json")
        page.locator("#three-interferometer").screenshot(path=str(out / "sequence-desktop.png"))
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
            page.locator("#three-interferometer").screenshot(
                path=str(out / f"sequence-{width}.png")
            )
        page.locator("#three-reset").click()
        expect(page.locator("#three-status")).to_have_text("Ready")
        assert float(page.locator("#three-time").inner_text()) == 0
        page.locator("#three-clear-pin").click()
        expect(page.locator("#three-export-pair")).to_be_disabled()
        report.update(errors=errors, api_requests=api)
        assert not errors, errors
        assert not api, api
        (out / "browser.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
