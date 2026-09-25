"""Exercise laboratory controls, scales, applicability, comparisons and replay."""

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
        page.evaluate("""() => {
            window.drawnPlots = {};
            const original = rawPlot;
            rawPlot = (...args) => { window.drawnPlots[args[0]] = args; original(...args); };
        }""")
        initial_time = page.locator("#time").inner_text()
        page.locator("#unit-mode").select_option("physical")
        expect(page.locator("#status")).to_have_text("Parameters changed")
        assert page.locator("#time").inner_text() == initial_time
        expect(page.locator("#interaction")).to_be_disabled()
        page.locator("#physical-controls summary").click()
        page.locator("#atoms").fill("100000")
        page.locator("#prepare").click()
        expect(page.locator("#error")).to_contain_text("Derived g exceeds 100")
        assert page.locator("#time").inner_text() == initial_time
        page.locator("#reset").click()
        expect(page.locator("#status")).to_have_text("Ready")
        expect(page.locator("#unit-mode")).to_have_value("dimensionless")
        expect(page.locator("#physical-readout")).to_be_hidden()

        page.get_by_text("Guided experiments", exact=True).click()

        def load(name):
            page.locator("#demo").select_option(name)
            page.locator("#load-demo").click()
            with page.expect_response(
                lambda r: r.url.endswith("/api") and r.request.method == "POST"
            ) as response:
                page.locator("#prepare").click()
            data = response.value.json()["result"]
            expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
            return data

        prepared = load("positive")
        u = prepared["physical"]
        assert abs(prepared["config"]["interaction"] - 22.0368757386) < 1e-8
        expect(page.locator("#regime-status")).to_have_text("Scale separation supported")
        expect(page.locator("#time")).to_contain_text("ms")
        expect(page.locator("#width")).to_contain_text("μm")
        expect(page.locator("#legend-label")).to_contain_text("ATOMS/μm²")
        assert abs(float(page.locator("#barrier_height").input_value()) - 240) < 1e-8
        plots = page.evaluate("window.drawnPlots")
        density = plots["profile"][1][0]["points"]
        assert (
            abs(density[64][1] - prepared["cross_section"][64] * 200 / u["length_um"] ** 2) < 1e-10
        )
        assert plots["widths"][5] == "t / ms"
        assert plots["potential-profile"][6] == "V/h / Hz"
        page.locator("#physical-controls").evaluate("e=>e.open=false")
        page.get_by_text("Guided experiments", exact=True).click()
        page.locator("#potential-overlay").check()
        page.locator("#run").click()
        expect(page.locator("#stage-hold")).to_have_class("active", timeout=60000)
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Paused")
        frozen = page.locator("#time").inner_text()
        page.wait_for_timeout(200)
        assert page.locator("#time").inner_text() == frozen
        page.locator("#step").click()
        expect(page.locator("#status")).to_have_text("Paused")
        delta = float(page.locator("#time").inner_text().split()[0]) - float(frozen.split()[0])
        assert abs(delta - prepared["config"]["dt"] * u["time_ms"]) < 0.0011
        page.screenshot(path=str(out / "physical-hold.png"), full_page=True)
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Complete", timeout=60000)
        expect(page.locator("#warning")).to_be_hidden()
        expect(page.locator("#potential-status")).to_contain_text("Trap released — V = 0")
        page.locator("#pin").click()
        expect(page.locator("#comparison")).to_be_visible()
        pinned = page.locator("#comparison-body tr td:nth-child(2)").all_text_contents()
        page.get_by_text("Guided experiments", exact=True).click()
        load("negative")
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Complete", timeout=60000)
        assert page.locator("#comparison-body tr td:nth-child(2)").all_text_contents() == pinned
        with page.expect_download() as download:
            page.locator("#export").click()
        path = out / "physical-comparison.json"
        download.value.save_as(path)
        exported = json.loads(path.read_text())
        evidence["comparison_replay"] = verify_export(exported)
        da, db = (exported[k]["history"][-1] for k in ("reference", "current"))
        assert abs(da["left_fraction"] + db["left_fraction"] - 1) < 1e-5
        assert abs(da["relative_phase"] + db["relative_phase"]) < 1e-5
        page.screenshot(path=str(out / "physical-comparison.png"), full_page=True)

        # Different physical scales must be applied independently to each plotted run.
        page.locator("#physical-controls summary").click()
        page.locator("#reference_hz").fill("40")
        expect(page.locator("#omega_x")).to_have_value("40")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        plots = page.evaluate("window.drawnPlots")
        profiles = plots["profile"][1]
        assert abs(profiles[0]["points"][0][0] / profiles[1]["points"][0][0] - 1 / 2**0.5) < 1e-6
        widths = plots["widths"][1]
        assert abs(widths[2]["points"][-1][0] - da["time"] * u["time_ms"]) < 1e-8
        evidence["independent_comparison_scales"] = True

        # Preserve physical config on reset after dirty input; detect loss of confinement.
        page.locator("#reference_hz").fill("50")
        page.locator("#reset").click()
        expect(page.locator("#reference_hz")).to_have_value("40")
        page.locator("#axial_hz").fill("20")
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#regime-status")).to_have_text("Outside the frozen-axial regime")
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            page.wait_for_timeout(200)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.screenshot(path=str(out / "physical-mobile.png"), full_page=True)
        coupling = page.evaluate("state.config.interaction")
        page.locator("#unit-mode").select_option("dimensionless")
        assert abs(float(page.locator("#interaction").input_value()) - coupling) < 1e-10
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#comparison-caption")).to_contain_text("use dimensionless units")
        assert page.evaluate("window.drawnPlots.profile[5]") == "x / a₀"

        notes = browser.new_page()
        notes.goto(args.url + "/physical-units")
        expect(notes.get_by_role("heading", name="Reference map")).to_be_visible()
        assert notes.locator('a[href="https://arxiv.org/abs/cond-mat/9806038"]').count() == 1
        notes.set_viewport_size({"width": 320, "height": 740})
        assert notes.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert not errors, errors
        evidence.update(
            {
                "page_errors": errors,
                "mobile_widths": [390, 320],
                "invalid_recovery": True,
                "applicability_warning": True,
            }
        )
        (out / "physical-browser-report.json").write_text(json.dumps(evidence, indent=2))
        print(json.dumps(evidence, indent=2))
        browser.close()


if __name__ == "__main__":
    main()
