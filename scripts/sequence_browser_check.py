"""Exercise split/hold/release, field overlays, and immutable run comparisons."""

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
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url + "#workspace")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        page.locator("#experiment").select_option("sequence")
        page.locator("#split_time").fill("2")
        page.locator("#hold_time").fill("1")
        page.locator("#expansion_time").fill("1.5")
        page.get_by_text("Numerical resolution", exact=True).click()
        page.locator("#dt").fill("0.01")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#sequence-clock")).to_have_text("0.00 / 4.50 ω₀⁻¹")
        expect(page.locator("#release")).to_be_disabled()
        page.get_by_text("Numerical resolution", exact=True).click()
        plain = page.locator("#field").evaluate("c=>c.toDataURL()")
        page.locator("#potential-overlay").check()
        assert plain != page.locator("#field").evaluate("c=>c.toDataURL()")
        page.locator("#run").click()
        expect(page.locator("#stage-hold")).to_have_class("active", timeout=30000)
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Paused")
        expect(page.locator("#sequence-live")).to_contain_text("Barrier 12.00")
        page.screenshot(path=str(out / "sequence-hold.png"), full_page=True)
        frozen = page.locator("#time").inner_text()
        page.wait_for_timeout(250)
        assert page.locator("#time").inner_text() == frozen
        before_step = float(frozen.split()[0])
        page.locator("#step").click()
        expect(page.locator("#status")).to_have_text("Paused")
        assert abs(float(page.locator("#time").inner_text().split()[0]) - before_step - 0.01) < 1e-8
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Complete", timeout=30000)
        expect(page.locator("#time")).to_contain_text("4.500")
        expect(page.locator("#sequence-stage")).to_have_text("Sequence complete")
        expect(page.locator("#run")).to_be_disabled()
        expect(page.locator("#step")).to_be_disabled()
        expect(page.locator("#warning")).not_to_be_visible()
        page.locator("#pin").click()
        expect(page.locator("#comparison")).to_be_visible()
        expect(page.locator("#pin")).to_have_text("Replace reference")
        reference_cells = page.locator("#comparison-body tr td:nth-child(2)").all_text_contents()
        page.locator("#bias").fill("-0.5")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        assert (
            page.locator("#comparison-body tr td:nth-child(2)").all_text_contents()
            == reference_cells
        )
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Complete", timeout=30000)
        assert (
            page.locator("#comparison-body tr td:nth-child(2)").all_text_contents()
            == reference_cells
        )
        assert (
            page.locator("#comparison-body tr td:nth-child(3)").all_text_contents()
            != reference_cells
        )
        with page.expect_download() as download:
            page.locator("#export").click()
        path = out / "sequence-comparison.json"
        download.value.save_as(path)
        data = json.loads(path.read_text())
        assert data["schema"] == "coldatomlab-comparison-v1"
        assert data["reference"]["config"]["bias"] == 0.5
        assert data["current"]["config"]["bias"] == -0.5
        assert data["reference"]["steps"] == 450 and data["current"]["steps"] == 450
        assert data["reference"]["release_step"] == 300
        evidence["comparison_replay"] = verify_export(data)
        page.screenshot(path=str(out / "sequence-comparison.png"), full_page=True)
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "sequence-mobile.png"), full_page=True)
        page.set_viewport_size({"width": 320, "height": 740})
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "sequence-mobile-320.png"), full_page=True)
        page.locator("#reset").click()
        expect(page.locator("#status")).to_have_text("Ready")
        expect(page.locator("#sequence-clock")).to_have_text("0.00 / 4.50 ω₀⁻¹")
        assert (
            page.locator("#comparison-body tr td:nth-child(2)").all_text_contents()
            == reference_cells
        )
        page.locator("#clear-reference").click()
        expect(page.locator("#comparison")).not_to_be_visible()
        expect(page.locator("#export")).to_have_text("Export run ↓")
        page.locator("#split_time").fill("8")
        page.locator("#hold_time").fill("6")
        page.locator("#expansion_time").fill("8")
        page.locator("#prepare").click()
        expect(page.locator("#error")).to_contain_text("must not exceed 18")
        page.locator("#reset").click()
        expect(page.locator("#status")).to_have_text("Ready")
        assert not errors, errors
        evidence.update(
            {
                "page_errors": errors,
                "timeline_and_automatic_release": True,
                "exact_completion": True,
                "potential_overlay": True,
                "immutable_reference": True,
                "invalid_duration_recovery": True,
                "mobile_no_overflow": True,
            }
        )
        browser.close()
    (out / "sequence-browser-report.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    print(json.dumps(evidence, indent=2))


if __name__ == "__main__":
    main()
