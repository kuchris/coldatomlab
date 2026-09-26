"""Local/static UI acceptance and hardware WebGPU checks for experiment 06."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.package_webgpu import main as package
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/vortex")


def exercise(browser, url, name):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "/vortex.html", wait_until="networkidle")
    assert page.url.endswith("/#vortex")
    f = page.frame_locator("#vortex-frame")
    expect(f.locator("#v-status")).to_contain_text("Ready to prepare", timeout=30000)
    f.locator("#v-form details summary").click()
    f.locator("#v-n").select_option("32")
    f.locator("#v-width").fill("1")
    f.locator("#v-duration").fill("0.104")
    # HTML step validity accepts 0.1; use a valid fractional endpoint below via the solver probe.
    f.locator("#v-duration").fill("0.1")
    f.locator("#v-prepare").click()
    expect(f.locator("#v-run")).to_be_enabled(timeout=30000)
    f.locator("#v-pin").click()
    pin = f.locator("#v-pin-phase").evaluate("c=>c.toDataURL()")
    f.locator("#v-step").click()
    expect(f.locator("#v-status")).to_contain_text("1 steps")
    f.locator("#v-run").click()
    expect(f.locator("#v-status")).to_contain_text("Complete", timeout=30000)
    expect(f.locator("#v-status")).to_contain_text("25 steps")
    with page.expect_download() as event:
        f.locator("#v-json").click()
    path = OUT / f"{name}-ui.json"
    event.value.save_as(path)
    result = verify_export(json.loads(path.read_text(encoding="utf8")))
    with page.expect_download() as event:
        f.locator("#v-csv").click()
    csv = OUT / f"{name}-ui.csv"
    event.value.save_as(csv)
    assert "flow_circulation_quanta" in csv.read_text(encoding="utf8")
    f.locator("#v-reset").click()
    expect(f.locator("#v-status")).to_contain_text("0 steps")
    f.locator('[data-vortex-preset="negative"]').click()
    f.locator("#v-prepare").click()
    expect(f.locator("#v-run")).to_be_enabled(timeout=30000)
    assert f.locator("#v-metrics").inner_text().count("-1") >= 1
    assert f.locator("#v-pin-phase").evaluate("c=>c.toDataURL()") == pin
    f.locator("#v-run").click()
    expect(f.locator("#v-pause")).to_be_enabled()
    f.locator("#v-pause").click()
    expect(f.locator("#v-run")).to_be_enabled(timeout=30000)
    paused = f.locator("#v-status").inner_text()
    page.wait_for_timeout(300)
    assert f.locator("#v-status").inner_text() == paused
    # Shell navigation preserves the existing workspace and immutable pin.
    page.locator('a[aria-label="Cold Atom Lab home"]').click()
    page.locator('a.open-experiment-link[href="#vortex"]').click()
    assert f.locator("#v-status").inner_text() == paused
    page.screenshot(path=str(OUT / f"{name}-desktop.png"), full_page=True)
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 850})
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
        assert f.locator("body").evaluate("el=>el.scrollWidth<=innerWidth+1")
        page.screenshot(path=str(OUT / f"{name}-{width}.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    # Existing quantum workspace remains usable, then return to vortex.
    page.goto(url + "/#quantum")
    expect(page.frame_locator("#quantum-frame").locator("#tm-status")).to_contain_text(
        "Ready", timeout=30000
    )
    page.goto(url + "/#vortex")
    f = page.frame_locator("#vortex-frame")
    expect(f.locator("#v-prepare")).to_be_enabled()
    frame = page.frame(url=url + "/vortex.html#embedded")
    probe = frame.evaluate("""async()=>{
      const s=await VortexGPU.create({n:32,width:1,duration:.103});
      while(!s.complete&&!s.warning)await s.advance(20);
      const result={adapter:s.adapter,steps:s.steps,d:s.history.at(-1)};
      await s.reset();const bad=s.initial.slice();for(let i=0;i<bad.length;i++)bad[i]*=1.01;
      s.device.queue.writeBuffer(s.fields[s.index],0,bad);await s.advance(20);result.normStop=s.warning;result.normStopSteps=s.steps;
      await s.reset();const edge=new Float32Array(s.count*2);edge[0]=1/Math.sqrt(s.dx**3);s.device.queue.writeBuffer(s.fields[s.index],0,edge);await s.advance(20);result.edgeStop=s.warning;
      s.destroy();try{await s.readField();}catch(e){result.deviceError=true;}return result;
    }""")
    assert probe["steps"] == 26 and probe["d"]["winding"] == 1 and not probe["adapter"]["fallback"]
    assert "norm drift" in probe["normStop"] and probe["normStopSteps"] == 1
    assert "boundary" in probe["edgeStop"] and probe["deviceError"]
    assert not errors, errors
    page.close()
    return {"replay": result, "probe": probe, "page_errors": errors, "viewports": [1440, 390, 320]}


def main():
    OUT.mkdir(exist_ok=True)
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
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
