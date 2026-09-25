"""Exercise actual camera controls, immutable comparisons and image replay."""

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
    evidence = {}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1100})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#capture")).to_be_disabled()
        page.get_by_text("Guided experiments", exact=True).click()
        page.locator("#demo").select_option("positive")
        page.locator("#load-demo").click()
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        page.locator("#run").click()
        expect(page.locator("#capture")).to_be_disabled()
        expect(page.locator("#status")).to_have_text("Complete", timeout=60000)
        source_time = page.locator("#time").inner_text()

        def capture():
            with page.expect_response(
                lambda r: r.url.endswith("/api") and '"capture"' in (r.request.post_data or "")
            ) as response:
                page.locator("#capture").click()
            result = response.value.json()
            assert response.value.ok, result
            expect(page.locator("#camera-result")).to_be_visible()
            expect(page.locator("#capture")).to_be_enabled()
            assert page.locator("#time").inner_text() == source_time
            return result["result"]

        page.locator("#camera-ideal").click()
        ideal = capture()
        for key in ("atoms", "width_x", "width_y", "fringe_spacing", "fringe_contrast"):
            assert abs(ideal["image"]["measured"][key] - ideal["image"]["truth"][key]) < 1e-9
        page.locator("#camera-pin").click()
        expect(page.locator("#camera-clear")).to_be_visible()
        pinned = page.locator("#camera-measurements tr td:last-child").all_text_contents()
        page.locator("#cam-fwhm_um").fill("4")
        expect(page.locator("#camera-caption")).to_contain_text("edits pending")
        blurred = capture()
        assert (
            blurred["image"]["measured"]["fringe_contrast"]
            < ideal["image"]["measured"]["fringe_contrast"] - 0.25
        )
        assert page.locator("#camera-measurements tr td:last-child").all_text_contents() == pinned
        page.locator(".camera-lab").screenshot(path=str(out / "camera-comparison.png"))
        page.locator("#cam-fwhm_um").fill("8")
        unresolved = capture()
        assert unresolved["image"]["measured"]["fringe_spacing"] is None
        expect(page.locator("#camera-warnings")).to_contain_text("No reliably resolved")
        page.locator("#cam-binning").select_option("8")
        page.locator("#cam-strip_um").fill("10")
        page.locator("#cam-fwhm_um").fill("0")
        coarse = capture()
        assert len(coarse["image"]["x_um"]) == 16
        assert coarse["image"]["measured"]["fringe_spacing"] is None

        page.locator("#cam-binning").select_option("2")
        page.locator("#cam-strip_um").fill("4")
        page.locator("#cam-fwhm_um").fill("1.5")
        page.locator("#cam-noise").check()
        first = capture()
        again = capture()
        assert first == again
        page.get_by_text("Detector & repeatability", exact=True).click()
        page.locator("#cam-seed").fill("18")
        noisy = capture()
        assert noisy["image"]["atoms_frame"] != first["image"]["atoms_frame"]
        assert noisy["source"] == ideal["source"]
        with page.expect_download() as download:
            page.locator("#camera-export").click()
        path = out / "camera-comparison.json"
        download.value.save_as(path)
        bundle = json.loads(path.read_text())
        assert bundle["reference"] == ideal and bundle["current"] == noisy
        evidence["camera_replay"] = verify_export(bundle)

        page.locator("#cam-saturation").fill("0.001")
        page.locator("#cam-exposure_us").fill("0.1")
        low = capture()
        assert low["image"]["invalid_roi_pixels"] > 0
        assert low["image"]["measured"]["atoms"] is None
        expect(page.locator("#camera-measurements tr").first.locator("td").nth(2)).to_have_text("—")
        page.locator("#cam-roi_um").fill("1")
        page.locator("#cam-binning").select_option("8")
        page.locator("#capture").click()
        expect(page.locator("#camera-caption")).to_contain_text("Capture failed")
        expect(page.locator("#status")).to_have_text("Complete")
        page.locator("#cam-roi_um").fill("20")
        page.locator("#cam-strip_um").fill("4")
        page.locator("#cam-saturation").fill("0.1")
        page.locator("#cam-exposure_us").fill("5")
        page.locator("#camera-ideal").click()
        capture()
        page.locator("#cam-fwhm_um").fill("4")
        capture()
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            page.wait_for_timeout(200)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator(".camera-lab").screenshot(path=str(out / "camera-mobile.png"))
        page.locator("#reset").click()
        expect(page.locator("#status")).to_have_text("Ready")
        expect(page.locator("#camera-caption")).to_contain_text("current simulation has changed")
        assert page.locator("#camera-measurements tr td:last-child").all_text_contents() == pinned
        page.locator("#camera-clear").click()
        expect(page.locator("#camera-clear")).to_be_hidden()
        expect(page.locator("#camera-export")).to_have_text("Export image ↓")
        with page.expect_download() as download:
            page.locator("#camera-export").click()
        download.value.save_as(out / "camera-single.json")
        assert (
            json.loads((out / "camera-single.json").read_text())["schema"]
            == "coldatomlab-camera-v1"
        )
        page.goto(args.url + "/imaging")
        expect(page.get_by_role("heading", name="Forward model")).to_be_visible()
        assert page.locator('a[href="https://arxiv.org/abs/0707.2930"]').count() == 1
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        evidence.update(
            {
                "page_errors": errors,
                "ideal_recovery": True,
                "same_state_acquisition": True,
                "contrasts": [
                    ideal["image"]["measured"]["fringe_contrast"],
                    blurred["image"]["measured"]["fringe_contrast"],
                ],
                "unresolved_at_8_um": True,
                "coarse_pixel_unresolved": True,
                "seed_repeatability": True,
                "invalid_recovery": True,
                "mobile_widths": [390, 320],
                "immutable_reference": True,
            }
        )
        (out / "camera-browser-report.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
