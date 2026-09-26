"""One-button experiment, cancellation and independent sequence replay."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.package_webgpu import main as package
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/vortex-sequence")


def exercise(browser, url, name):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "/#vortex", wait_until="networkidle")
    f = page.frame_locator("#vortex-frame")
    expect(f.locator("#v-stationary")).to_have_value("1")
    expect(f.locator("#v-n")).to_have_value("128")
    f.locator("#v-n").select_option("32")
    f.locator("#v-length").evaluate("el=>{el.closest('details').open=true}")
    f.locator("#v-length").fill("16")
    f.locator("#v-width").fill("1")
    f.locator("#v-hold-ms").fill("0.37")
    f.locator("#v-tof-ms").fill("0.41")
    f.locator("#v-sequence-run").click()
    f.locator("#vi-seed").fill("19")  # Current acquisition was frozen at Start.
    expect(f.locator("#v-sequence-status")).to_contain_text("Complete", timeout=60000)
    expect(f.locator("#v-protocol")).to_contain_text("trap OFF")
    expect(f.locator("#vi-status")).to_contain_text("Image captured")
    f.locator("#v-compare-runs").click()
    with page.expect_download() as event:
        f.locator("#v-run-list button").first.click()
    path = OUT / f"{name}-sequence.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    assert data["protocol"]["hold_steps"] == 29 and data["protocol"]["tof_steps"] == 32
    assert data["image"]["image"]["camera"]["seed"] == 17
    assert "source" not in data["image"]  # One shared source in the sequence file.
    replay = verify_export(data)
    first_curve = f.locator("#v-paper-plot").evaluate("c=>c.toDataURL()")
    f.locator("#v-paper-quantity").select_option("radial_rms")
    assert f.locator("#v-paper-plot").evaluate("c=>c.toDataURL()") != first_curve
    original = f.locator("#v-run-list article").first.inner_text()
    f.locator("#v-tof-ms").fill("0.65")
    f.locator("#v-sequence-run").click()
    expect(f.locator("#v-run-list article")).to_have_count(2, timeout=60000)
    assert f.locator("#v-run-list article").first.inner_text() == original
    # Cancel a newly preparing state; previous verified results remain.
    f.locator("#v-n").select_option("64")
    f.locator("#v-sequence-run").click()
    expect(f.locator("#v-sequence-stop")).to_be_enabled()
    f.locator("#v-sequence-stop").click()
    expect(f.locator("#v-sequence-status")).to_contain_text(
        "Stopped during preparation", timeout=30000
    )
    expect(f.locator("#v-run-list article")).to_have_count(2)
    # Stop an evolution, and export its actual partial state without an image.
    f.locator('[data-vortex-preset="imaging"]').click()
    f.locator("#v-hold-ms").fill("40")
    f.locator("#v-sequence-run").click()
    expect(f.locator("#v-sequence-status")).to_contain_text("Holding", timeout=30000)
    f.locator("#v-sequence-stop").click()
    expect(f.locator("#v-sequence-status")).to_contain_text("partial run saved", timeout=30000)
    with page.expect_download() as event:
        f.locator("#v-run-list button").last.click()
    path = OUT / f"{name}-stopped.json"
    event.value.save_as(path)
    stopped = verify_export(json.loads(path.read_text(encoding="utf8")))
    # Navigating away requests a stop and retains the three most recent runs.
    f.locator("#v-sequence-run").click()
    expect(f.locator("#v-sequence-status")).to_contain_text("Holding", timeout=30000)
    page.locator('a[aria-label="Cold Atom Lab home"]').click()
    expect(f.locator("#v-sequence-status")).to_contain_text("partial run saved", timeout=30000)
    page.locator('a.open-experiment-link[href="#vortex"]').click()
    expect(f.locator("#v-run-list article")).to_have_count(3)
    assert f.locator("#v-run-list article").first.inner_text().startswith("Run 2")
    page.screenshot(path=str(OUT / f"{name}-desktop.png"), full_page=True)
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 850})
        assert f.locator("body").evaluate("el=>el.scrollWidth<=innerWidth+1")
        page.screenshot(path=str(OUT / f"{name}-{width}.png"), full_page=True)
    frame = page.frame(url=url + "/vortex.html#embedded")
    negative = frame.evaluate("""async()=>{
      const s=await VortexGPU.create({n:32,width:1,stationary:1,charge:-1,
        g:80*Math.PI,radial_hz:75,axial_hz:75,duration:.1,tof_duration:.1});
      await s.advance(20); await s.advance(5); await s.release();
      await s.advance(20); await s.advance(5);
      const result=s.export(); s.destroy(); return result;
    }""")
    negative_replay = verify_export(negative)
    assert negative_replay["diagnostics"]["winding"] == -1
    assert not errors, errors
    page.close()
    return dict(complete=replay, stopped=stopped, negative=negative_replay, errors=errors)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    package()
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        with serve() as url:
            report["local"] = exercise(browser, url, "local")
        with tempfile.TemporaryDirectory() as directory:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as archive:
                archive.extractall(directory)
            with serve(directory) as url:
                report["static"] = exercise(browser, url, "static")
        browser.close()
    (OUT / "browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print("One-button local/static sequences, preparation/evolution stop and replay passed.")


if __name__ == "__main__":
    main()
