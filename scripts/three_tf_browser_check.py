"""Exercise the full strong-interaction preset in Chromium."""

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
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url + "/#lab3d")
        page.wait_for_load_state("networkidle")
        page.locator("#three-engine").select_option("cpu")
        page.evaluate("""() => {
          const original=window.fetch;
          window.fetch=async (...args) => {
            const r=await original(...args);
            if(args[0]==='/api3d' && r.ok) window.last3D=(await r.clone().json()).result;
            return r;
          };
        }""")
        page.locator("#three-preset").select_option("tf")
        page.locator("#three-load").click()
        page.locator("#three-prepare").click()
        expect(page.locator("#three-status")).to_have_text("Ready", timeout=300000)
        initial = page.evaluate("window.last3D.diagnostics")
        assert initial["aspect_xz"] < 1 and initial["aspect_yz"] < 1
        page.locator("#three-release").click()
        expect(page.locator("#three-trap")).to_have_text("All axes released")
        page.locator("#three-run").click()
        expect(page.locator("#three-status")).to_have_text("Complete", timeout=300000)
        result = page.evaluate("window.last3D")
        d = result["diagnostics"]
        assert d["steps"] == 750 and not result["warning"]
        assert d["aspect_xz"] > 1 and d["aspect_yz"] > 1
        assert abs(d["norm"] - 1) < 1e-10
        assert result["preparation"]["relative_stationary_residual"] < 1e-5
        page.locator("#three-columns").click()
        expect(page.locator("#three-image-note")).to_contain_text("atoms / µm²")
        page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
        page.screenshot(path=str(out / "3d-tf-desktop.png"), full_page=True)
        assert not errors, errors
        (out / "3d-tf-browser-result.json").write_text(json.dumps(result, indent=2))
        browser.close()
    print(
        "Thomas-Fermi browser preset passed: 96^3 interacting release, shape inversion, projections."
    )


if __name__ == "__main__":
    main()
