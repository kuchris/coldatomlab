"""Exercise actual 3D browser state, rendering, controls and exported replay."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1100}, accept_downloads=True)
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url + "/#lab3d")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#three-status")).to_have_text("Not prepared")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        old = page.evaluate("JSON.stringify({session,state})")
        page.evaluate("""() => {
          window.__threeStates=[];
          const original=window.fetch;
          window.fetch=async (...args) => {
            const response=await original(...args);
            if(args[0]==='/api3d' && response.ok)
              window.__threeStates.push((await response.clone().json()).result);
            return response;
          };
        }""")

        def latest():
            return page.evaluate("window.__threeStates.at(-1)")

        page.locator("#three-preset").select_option("gaussian")
        page.locator("#three-load").click()
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=180000)
        assert latest()["config"]["scattering_nm"] == 0
        canvas = page.locator("#three-surface")
        before = canvas.screenshot()
        canvas.focus()
        page.keyboard.press("ArrowRight")
        assert canvas.screenshot() != before
        box = canvas.bounding_box()
        page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        page.mouse.down()
        page.mouse.move(
            box["x"] + box["width"] / 2 + 80, box["y"] + box["height"] / 2 + 30, steps=8
        )
        page.mouse.up()
        after = canvas.screenshot()
        page.locator("#three-iso").fill("40")
        page.locator("#three-iso").dispatch_event("input")
        assert canvas.screenshot() != after
        page.locator("#three-zoom").fill("3")
        page.locator("#three-zoom").dispatch_event("input")
        page.locator("#three-home").click()
        expect(page.locator("#three-zoom")).to_have_value("1")
        page.locator("#three-release").click()
        expect(page.locator("#three-trap")).to_have_text("All axes released")
        page.locator("#three-step").click()
        expect(page.locator("#three-status")).to_have_text("Paused")
        assert latest()["diagnostics"]["steps"] == 1
        page.locator("#three-run").click()
        page.wait_for_timeout(650)
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Paused", timeout=30000)
        stopped = latest()["diagnostics"]["steps"]
        page.wait_for_timeout(450)
        assert latest()["diagnostics"]["steps"] == stopped
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Complete", timeout=180000)
        assert latest()["diagnostics"]["steps"] == 500
        for row in page.locator("#three-theory-table tr").all():
            assert abs(float(row.locator("td").nth(3).inner_text().strip("%"))) < 0.001
        pixels = page.locator("#three-xy").screenshot()
        page.locator("#three-columns").click()
        assert page.locator("#three-xy").screenshot() != pixels
        expect(page.locator("#three-image-note")).to_contain_text("atoms / µm²")
        page.locator("#three-slices").click()
        expect(page.locator("#three-image-note")).to_contain_text("atoms / µm³")
        with page.expect_download() as download:
            page.locator("#three-export").click()
        file = out / "3d-browser-export.json"
        download.value.save_as(file)
        replay = verify_export(json.loads(file.read_text()))
        assert replay["max_wavefunction_error"] < 1e-12
        # Invalid preparation must retain the completed field and allow Reset.
        page.locator("#three-fx_hz").fill("200")
        page.locator("#three-prepare").click()
        expect(page.locator("#three-error")).to_be_visible()
        page.locator("#three-reset").click()
        expect(page.locator("#three-status")).to_have_text("Ready")
        expect(page.locator("#three-fx_hz")).to_have_value("30")
        assert latest()["diagnostics"]["steps"] == 0
        # Prepare and evolve an interacting field through the UI, not just a Gaussian.
        page.locator("#three-preset").select_option("interacting")
        page.locator("#three-load").click()
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=240000)
        assert latest()["scales"]["interaction"] > 600
        assert latest()["preparation"]["iterations"] > 0
        page.locator("#three-release").click()
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Complete", timeout=240000)
        final = latest()
        assert not final["warning"]
        assert final["diagnostics"]["widths"][0] > final["history"][0]["widths"][0]
        page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
        page.screenshot(path=str(out / "3d-desktop.png"), full_page=True)
        page.locator('[data-route="workspace"]').click()
        assert page.evaluate("JSON.stringify({session,state})") == old
        page.locator('[data-route="lab3d"]').click()
        expect(page.locator("#three-status")).to_have_text("Complete")
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
            page.screenshot(path=str(out / f"3d-mobile-{width}.png"), full_page=True)
        assert not errors, errors
        result = {
            "browser": "Chromium",
            "gaussian_replay": replay,
            "interacting_final": final["diagnostics"],
            "errors": errors,
        }
        (out / "3d-browser-result.json").write_text(json.dumps(result, indent=2))
        browser.close()
    print(
        "3D browser checks passed: controls, rendering, views, replay, errors, navigation, mobile."
    )


if __name__ == "__main__":
    main()
