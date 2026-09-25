"""Verify paper comparison, download, failure recovery and preserved lab state."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1050})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(args.url + "/#workspace")
        page.wait_for_load_state("networkidle")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        page.locator("#step").click()
        expect(page.locator("#status")).to_have_text("Paused")
        page.locator("#pin").click()
        expect(page.locator("#comparison")).to_be_visible()
        before = page.evaluate("JSON.stringify({session, state, reference})")
        page.route("**/api/benchmark", lambda route: route.fulfill(status=503, body="test failure"))
        page.locator('[data-route="benchmark"]').click()
        expect(page.locator("#benchmark-retry")).to_be_visible()
        expect(page.locator("#benchmark-status")).to_contain_text("workspace is unchanged")
        page.unroute("**/api/benchmark")
        page.locator("#benchmark-retry").click()
        expect(page.locator("#benchmark-result")).to_be_visible(timeout=60000)
        expect(page.locator("#benchmark-fit")).to_have_text("40.057 µm")
        expect(page.locator("#benchmark-difference")).to_have_text("-3.48%")
        expect(page.locator("#benchmark-comparison tr")).to_have_count(5)
        assert page.evaluate("JSON.stringify({session, state, reference})") == before
        with page.expect_download() as download:
            page.locator("#benchmark-export").click()
        download.value.save_as(out / "shin-browser-export.json")
        data = json.loads((out / "shin-browser-export.json").read_text(encoding="utf-8"))
        assert data["schema"] == "coldatomlab-shin-benchmark-v1"
        assert data["published"]["measurement_uncertainty_um"] is None
        assert data["base"]["analytic_wavefunction_l2_error"] < 1e-7
        assert data["comparison"][0]["period_um"] == data["base"]["fit"]["period_um"]
        page.locator("#paper-benchmark .benchmark-checks summary").click()
        expect(page.locator("#benchmark-checks tr")).to_have_count(5)
        page.evaluate("window.scrollTo(0, 0)")
        page.screenshot(path=str(out / "benchmark-desktop.png"), full_page=True)
        page.go_back()
        expect(page.locator("#lab-workbench")).to_be_visible()
        assert page.evaluate("JSON.stringify({session, state, reference})") == before
        # A direct link must work before any library navigation occurs.
        page.goto(args.url + "/#benchmark")
        expect(page.locator("#benchmark-result")).to_be_visible(timeout=60000)
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 850})
            expect(page.locator("#benchmark-profile")).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(out / f"benchmark-mobile-{width}.png"), full_page=True)
        assert not errors, errors
        browser.close()
    (out / "benchmark-browser-report.json").write_text(
        json.dumps(
            {
                "live_calculation_and_export": True,
                "error_recovery": True,
                "preserves_state_and_reference": True,
                "direct_link": True,
                "mobile_widths": [390, 320],
                "page_errors": errors,
            },
            indent=2,
        )
    )
    print("Benchmark browser checks passed.")


if __name__ == "__main__":
    main()
