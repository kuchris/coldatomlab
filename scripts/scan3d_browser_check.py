"""Exercise scan UI and fresh hardware WebGPU experiments; optional float64 replay."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8766/gpu.html")
    parser.add_argument("--refine", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--defaults", action="store_true")
    parser.add_argument("--out", type=Path, default=Path("artifacts/scan3d"))
    args = parser.parse_args()
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    evidence = dict(scans={})
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        page = browser.new_page(viewport=dict(width=1500, height=1000), accept_downloads=True)
        errors, api = [], []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on("request", lambda r: api.append(r.url) if "/api" in r.url else None)
        page.goto(args.url)
        page.wait_for_load_state("networkidle")

        def export(button, name):
            with page.expect_download() as dl:
                page.locator(button).click()
            path = out / name
            dl.value.save_as(path)
            return json.loads(path.read_text()) if name.endswith(".json") else path.read_text()

        page.locator("#three-preset").select_option("camera")
        page.locator("#three-load").click()
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=60000)
        before = export("#three-export", "manual-before.json")

        if args.defaults:
            page.locator("#scan3d-start-run").click()
            expect(page.locator("#scan3d-status")).to_have_text("Scan complete.", timeout=180000)
            default = export("#scan3d-json", "default-calibration.json")
            assert len(default["records"]) == 5
            assert all(
                r["summary"]["mean_phase"] is not None
                and abs(r["summary"]["ideal_minus_guide"]) < 0.04
                for r in default["records"]
            )
            evidence["default_calibration"] = [r["summary"] for r in default["records"]]

        # Invalid batch settings must preserve the current manual experiment.
        page.locator("#scan3d-points").fill("9")
        page.locator("#scan3d-repeats").fill("20")
        page.locator("#scan3d-start-run").click()
        expect(page.locator("#scan3d-error")).to_contain_text("80 exposures")
        page.locator("#scan3d-points").fill("3")
        page.locator("#scan3d-repeats").fill("3")
        page.locator("#scan3d-start").fill("-1")
        page.locator("#scan3d-end").fill("1")

        def finish(name):
            expect(page.locator("#scan3d-status")).to_have_text("Scan complete.", timeout=180000)
            expect(page.locator("#scan3d-start-run")).to_be_enabled()
            data = export("#scan3d-json", f"{name}.json")
            evidence["scans"][name] = [
                {k: r.get(k) for k in ("point", "value", "grid", "status", "summary")}
                for r in data["records"]
            ]
            assert data["status"] == "complete", data
            return data

        page.locator("#scan3d-start-run").click()
        expect(page.locator("#three-run")).to_be_disabled()
        expect(page.locator("#camera3d-capture")).to_be_disabled()
        expect(page.locator("#scan3d-status")).to_contain_text("evolving", timeout=60000)
        page.locator("#scan3d-pause").click()
        expect(page.locator("#scan3d-pause")).to_have_text("Resume")
        page.wait_for_timeout(700)
        held = page.locator("#scan3d-status").inner_text()
        page.wait_for_timeout(350)
        assert page.locator("#scan3d-status").inner_text() == held
        page.locator("#scan3d-pause").click()
        phase = finish("phase")
        assert all(
            r["summary"]["valid"] == 3 and abs(r["summary"]["ideal_minus_guide"]) < 0.03
            for r in phase["records"]
        )
        assert all(abs(r["summary"]["camera_minus_ideal"]) < 0.15 for r in phase["records"])
        csv = export("#scan3d-csv", "phase.csv")
        assert "mean_phase_rad" in csv and len(csv.strip().splitlines()) == 4
        page.locator("#scan3d-panel").screenshot(path=str(out / "phase-desktop.png"))
        for width in (390, 320):
            page.set_viewport_size(dict(width=width, height=844))
            assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
            page.locator("#scan3d-panel").screenshot(path=str(out / f"phase-{width}.png"))
        page.set_viewport_size(dict(width=1500, height=1000))

        # Same seeds and fresh evolution reproduce the acquired data.
        page.locator("#scan3d-start-run").click()
        repeat = finish("repeat")
        assert [r["shots"] for r in phase["records"]] == [r["shots"] for r in repeat["records"]]
        page.locator("#scan3d-mode").select_option("bias")
        page.locator("#scan3d-start-run").click()
        bias = finish("bias")
        assert all(
            r["status"] == "complete" and r["summary"]["valid"] == 3 for r in bias["records"]
        )
        assert bias["records"][0]["summary"]["ideal_phase"] > 0.5
        assert bias["records"][-1]["summary"]["ideal_phase"] < -0.5
        page.locator("#scan3d-mode").select_option("hold")
        page.locator("#scan3d-start-run").click()
        hold = finish("hold")
        assert all(
            r["status"] == "complete" and r["summary"]["valid"] >= 2 for r in hold["records"]
        )
        assert (
            hold["records"][-1]["summary"]["ideal_phase"]
            < hold["records"][0]["summary"]["ideal_phase"] - 0.3
        )

        # Unavailable data is retained, not substituted with the input phase.
        page.locator("#scan3d-mode").select_option("phase")
        page.locator("#scan3d-points").fill("2")
        page.locator("#scan3d-repeats").fill("1")
        page.locator("#scan3d-axis").select_option("x")
        page.locator("#scan3d-start-run").click()
        missing = finish("unresolved")
        assert all(
            r["summary"]["failed"] == 1 and r["summary"]["mean_phase"] is None
            for r in missing["records"]
        )
        page.locator("#scan3d-axis").select_option("z")
        page.locator("#scan3d-points").fill("3")
        page.locator("#scan3d-start-run").click()
        expect(page.locator("#scan3d-summary")).to_contain_text(
            "1/3 evolutions completed", timeout=60000
        )
        page.locator("#scan3d-cancel").click()
        expect(page.locator("#scan3d-start-run")).to_be_enabled(timeout=60000)
        cancelled = export("#scan3d-json", "cancelled.json")
        assert cancelled["status"] == "cancelled" and 0 < len(cancelled["records"]) < 3
        if args.refine:
            page.locator("#scan3d-points").fill("2")
            page.locator("#scan3d-start").fill("0.2")
            page.locator("#scan3d-end").fill("0.8")
            page.locator("#scan3d-noise").uncheck()
            page.locator("#scan3d-refine").check()
            page.locator("#scan3d-start-run").click()
            refined = finish("refinement")
            assert len(refined["refinement"]) == 2
            assert all(
                max(abs(x) for x in r["width_relative"]) < 0.005 for r in refined["refinement"]
            )
            page.locator("#scan3d-panel").screenshot(path=str(out / "refinement-desktop.png"))
            evidence["refinement"] = refined["refinement"]
        assert export("#three-export", "manual-after.json") == before
        assert not errors, errors
        if "gpu.html" in args.url:
            assert not api, api
        evidence.update(page_errors=errors, api_requests=api, manual_state_unchanged=True)
        browser.close()
    if args.verify:
        from coldatomlab.scan3d import verify_scan

        evidence["replay"] = {}
        for name in ["phase", "bias", "hold", "unresolved", "cancelled"] + (
            ["refinement"] if args.refine else []
        ):
            print(f"Independent replay: {name}", flush=True)
            result = verify_scan(json.loads((out / f"{name}.json").read_text()))
            evidence["replay"][name] = result
            (out / f"{name}-replay.json").write_text(json.dumps(result, indent=2))
    (out / "browser.json").write_text(json.dumps(evidence, indent=2))
    print("Scan browser checks passed.")


if __name__ == "__main__":
    main()
