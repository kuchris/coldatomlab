"""Actual local/static vortex release and camera controls on hardware WebGPU."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.package_webgpu import main as package
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/vortex-imaging")


def exercise(browser, url, name):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "/#vortex", wait_until="networkidle")
    f = page.frame_locator("#vortex-frame")
    f.locator("#v-manual-prepare summary").click()
    f.locator("#v-manual summary").click()
    f.locator('[data-vortex-preset="imaging"]').click()
    f.locator("#v-prepare").click()
    expect(f.locator("#v-release")).to_be_enabled(timeout=30000)
    expect(f.locator("#v-applied")).to_contain_text("N = 1000")
    f.locator("#v-release").click()
    expect(f.locator("#v-protocol")).to_contain_text("trap OFF")
    expect(f.locator("#v-release")).to_be_disabled()
    f.locator("#v-run").click()
    expect(f.locator("#v-status")).to_contain_text("Complete", timeout=60000)
    expect(f.locator("#v-status")).to_contain_text("500 steps")
    state = f.locator("#v-metrics").inner_text()
    f.locator("#vi-capture").click()
    expect(f.locator("#vi-status")).to_contain_text("density dip resolved")
    assert f.locator("#v-metrics").inner_text() == state
    ideal = f.locator("#vi-measurements").inner_text()
    assert "0.901" in ideal
    with page.expect_download() as event:
        f.locator("#vi-json").click()
    path = OUT / f"{name}-image.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    replay = verify_export(data)
    with page.expect_download() as event:
        f.locator("#vi-csv").click()
    csv = OUT / f"{name}-profile.csv"
    event.value.save_as(csv)
    assert "camera," in csv.read_text(encoding="utf8")
    f.locator("#vi-pin").click()
    pin = f.locator("#vi-pin-image").evaluate("c=>c.toDataURL()")
    f.locator("#vi-blur").click()
    assert f.locator("#vi-measurements").inner_text() == ideal
    f.locator("#vi-capture").click()
    expect(f.locator("#vi-measurements")).to_contain_text("0.423")
    assert f.locator("#vi-pin-image").evaluate("c=>c.toDataURL()") == pin
    f.locator("#vi-ideal").click()
    f.locator("#vi-noise").select_option("on")
    f.locator("#vi-capture").click()
    noise = f.locator("#vi-camera").evaluate("c=>c.toDataURL()")
    f.locator("#vi-capture").click()
    assert f.locator("#vi-camera").evaluate("c=>c.toDataURL()") == noise
    f.locator("#vi-seed").fill("18")
    f.locator("#vi-capture").click()
    assert f.locator("#vi-camera").evaluate("c=>c.toDataURL()") != noise
    f.locator("#vi-axis").select_option("x")
    f.locator("#vi-capture").click()
    expect(f.locator("#vi-status")).to_contain_text("viewed along z")
    expect(f.locator("#vi-measurements")).to_contain_text("Unavailable")
    f.locator("#vi-axis").select_option("z")
    f.locator("#vi-ideal").click()
    f.locator("#vi-capture").click()
    frozen = f.locator("#vi-applied").inner_text()
    image = f.locator("#vi-camera").evaluate("c=>c.toDataURL()")
    f.locator("#v-reset").click()
    expect(f.locator("#v-protocol")).to_contain_text("trap ON")
    assert f.locator("#vi-applied").inner_text() == frozen
    assert f.locator("#vi-camera").evaluate("c=>c.toDataURL()") == image
    page.locator('a[aria-label="Cold Atom Lab home"]').click()
    page.locator('a.open-experiment-link[href="#vortex"]').click()
    assert f.locator("#vi-camera").evaluate("c=>c.toDataURL()") == image
    page.screenshot(path=str(OUT / f"{name}-desktop.png"), full_page=True)
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 850})
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        assert f.locator("body").evaluate("el=>el.scrollWidth<=innerWidth+1")
        page.screenshot(path=str(OUT / f"{name}-{width}.png"), full_page=True)
    assert not errors, errors
    # Exercise release during an active beam with interactions retained, plus
    # partial replay and rounding of a non-integral TOF endpoint.
    probes = f.locator("body").evaluate("""async () => {
      const s=await VortexGPU.create({...VortexModel.defaults,n:32,width:1,g:10,height:4,tof_duration:.103});
      await s.advance(7); await s.release(); await s.advance(5);
      const partial=s.export();
      while(!s.complete&&!s.warning) await s.advance(20);
      const full=s.export(); s.destroy(); return {partial,full};
    }""")
    assert probes["full"]["steps"] == 33 and probes["full"]["release_step"] == 7
    assert probes["full"]["config"]["g"] == 10
    protocol_replay = {key: verify_export(value) for key, value in probes.items()}
    assert not errors, errors
    page.close()
    return dict(
        replay=replay,
        errors=errors,
        viewports=[1440, 390, 320],
        capture_preserves_solver=True,
        pin_immutable=True,
        release_protocol=protocol_replay,
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    package()
    report = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        with serve() as url:
            report["local"] = exercise(browser, url, "local")
        with tempfile.TemporaryDirectory() as directory:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as z:
                z.extractall(directory)
            with serve(directory) as url:
                report["static"] = exercise(browser, url, "static")
        browser.close()
    (OUT / "browser.json").write_text(json.dumps(report, indent=2), encoding="utf8")
    print("Local and static TOF camera workflows verified.")


if __name__ == "__main__":
    main()
