"""Exercise the real local UI. Start the server before running this script."""

import argparse
import json
from pathlib import Path

import numpy as np
from playwright.sync_api import expect, sync_playwright

from coldatomlab.solver import replay


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    evidence = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100}, device_scale_factor=1)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        page.screenshot(path=str(out / "desktop-initial.png"), full_page=True)
        initial_canvas = page.locator("#field").evaluate("c => c.toDataURL()")
        initial_width = float(page.locator("#width").inner_text().split()[0])
        page.get_by_role("button", name="Release trap", exact=True).click()
        expect(page.locator("#trap-state")).to_have_text("TRAP OFF / EXPANDING")
        page.locator("#run").click()
        page.wait_for_function("parseFloat(document.getElementById('time').textContent) >= 0.4")
        page.get_by_role("button", name="Pause", exact=False).click()
        expect(page.locator("#status")).to_have_text("Paused")
        frozen_time = page.locator("#time").inner_text()
        # An observation interval verifies that paused time stays frozen.
        page.wait_for_timeout(350)
        assert page.locator("#time").inner_text() == frozen_time
        assert float(page.locator("#width").inner_text().split()[0]) > initial_width
        assert page.locator("#field").evaluate("c => c.toDataURL()") != initial_canvas
        previous = float(frozen_time.split()[0])
        page.get_by_role("button", name="Step", exact=True).click()
        expect(page.locator("#status")).to_have_text("Paused")
        assert abs(float(page.locator("#time").inner_text().split()[0]) - previous - 0.005) < 1e-8
        with page.expect_download() as download:
            page.get_by_role("button", name="Export run", exact=False).click()
        export_path = out / "single-run.json"
        download.value.save_as(export_path)
        data = json.loads(export_path.read_text())
        recreated = replay(data)
        saved = np.asarray(data["psi_real"]) + 1j * np.asarray(data["psi_imag"])
        error = float(np.max(np.abs(recreated.psi - saved)))
        assert error < 1e-12
        evidence["single_run"] = {
            "time": data["history"][-1]["time"],
            "replay_error": error,
            "pause_holds_time": True,
            "single_step": True,
        }
        page.get_by_role("button", name="Reset", exact=False).click()
        expect(page.locator("#status")).to_have_text("Ready")
        expect(page.locator("#trap-state")).to_have_text("TRAP ON / CONFINED")
        assert page.locator("#field").evaluate("c => c.toDataURL()") == initial_canvas

        # Rejected numerical settings must leave the previous experiment usable.
        page.get_by_text("Numerical resolution", exact=True).click()
        page.locator("#n").select_option("64")
        page.locator("#length").select_option("64")
        expect(page.locator("#run")).to_be_disabled()
        page.locator("#prepare").click()
        expect(page.locator("#error")).to_contain_text("finer grid")
        page.locator("#length").select_option("32")
        page.locator("#n").select_option("128")
        page.locator("#experiment").select_option("double")
        page.locator("#interaction").fill("0")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#experiment-title")).to_have_text("Matter-wave interference")
        expect(page.locator("#release")).to_be_disabled()
        page.get_by_text("Numerical resolution", exact=True).click()
        centers = []
        for phase in (0, 1):
            if phase:
                page.get_by_role("button", name="Opposite", exact=False).click()
                page.locator("#prepare").click()
                expect(page.locator("#status")).to_have_text("Ready")
            page.locator("#run").click()
            page.wait_for_function("parseFloat(document.getElementById('time').textContent) >= 2")
            page.get_by_role("button", name="Pause", exact=False).click()
            expect(page.locator("#status")).to_have_text("Paused")
            with page.expect_download() as download:
                page.locator("#export").click()
            path = out / f"interference-{phase}.json"
            download.value.save_as(path)
            export = json.loads(path.read_text())
            n = export["config"]["n"] // 2
            centers.append(export["psi_real"][n][n] ** 2 + export["psi_imag"][n][n] ** 2)
            if phase == 0:
                page.screenshot(path=str(out / "desktop-interference.png"), full_page=True)
        assert centers[0] > 0.002 and centers[1] < centers[0] * 1e-12
        evidence["interference_center_density"] = centers
        before_phase = page.locator("#field").evaluate("c => c.toDataURL()")
        page.get_by_role("button", name="Phase", exact=True).click()
        expect(page.locator("#phase-view")).to_have_attribute("aria-pressed", "true")
        assert page.locator("#field").evaluate("c => c.toDataURL()") != before_phase
        page.get_by_role("button", name="About the model", exact=False).click()
        expect(page.locator("#model-dialog")).to_be_visible()
        page.keyboard.press("Escape")
        expect(page.locator("#model-dialog")).not_to_be_visible()
        page.screenshot(path=str(out / "desktop-phase.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "mobile.png"), full_page=True)
        expect(page.locator("#prepare")).to_be_visible()
        page.set_viewport_size({"width": 320, "height": 740})
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "mobile-320.png"), full_page=True)
        # Check that the boundary stop propagates through the actual run loop.
        page.get_by_text("Numerical resolution", exact=True).click()
        page.locator("#n").select_option("64")
        page.locator("#length").select_option("24")
        page.locator("#dt").fill("0.02")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready")
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Stopped", timeout=30000)
        expect(page.locator("#warning")).to_contain_text("boundary")
        expect(page.locator("#run")).to_be_disabled()
        page.locator("#reset").click()
        expect(page.locator("#status")).to_have_text("Ready")
        expect(page.locator("#warning")).not_to_be_visible()
        assert not errors, errors
        evidence.update(
            {
                "page_errors": errors,
                "invalid_settings_recover": True,
                "phase_view": True,
                "mobile_no_horizontal_overflow": True,
                "boundary_stop_and_recovery": True,
            }
        )
        browser.close()
    (out / "browser-report.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
