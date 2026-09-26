"""Live local/static phase-readout controls and independently replayed exports."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/readout")


def export(page, name, button="rd-json"):
    with page.expect_download() as event:
        page.frame_locator("#quantum-frame").locator(f"#{button}").click()
    path = OUT / f"{name}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    check = verify_export(data)
    (OUT / f"{name}-replay.json").write_text(json.dumps(check, indent=2), encoding="utf8")
    return data


def run(frame):
    frame.locator("#rd-run").click()
    expect(frame.locator("#rd-status")).to_contain_text("Complete", timeout=60000)


def exercise(browser, url, prefix):
    page = browser.new_page(viewport=dict(width=1440, height=1000), accept_downloads=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(url + "/quantum.html", wait_until="networkidle")
    assert page.url.endswith("/#quantum")
    frame = page.frame_locator("#quantum-frame")
    expect(frame.locator("#tm-status")).to_contain_text("Ready", timeout=30000)
    frame.locator("#tm-step").click()
    frame.locator("#tm-pin").click()
    manual = export(page, prefix + "-manual-before", "tm-json")
    earlier = {}
    for name, count in [("ep", "count"), ("se", "preparations"), ("fp", "preparations")]:
        frame.locator(f"#{name}-{count}").fill("2")
        frame.locator(f"#{name}-run").click()
        expect(frame.locator(f"#{name}-status")).to_contain_text("Complete", timeout=60000)
        earlier[name] = export(page, prefix + f"-{name}-before", f"{name}-json")
    frame.get_by_role("button", name="Phase readout ↓", exact=True).click()
    frame.locator("#rd-run").click()
    expect(frame.locator("#rd-status")).to_contain_text("settings completed")
    frame.locator("#rd-pause").click()
    expect(frame.locator("#rd-status")).to_contain_text("Paused")
    count = frame.locator("#rd-point option").count()
    page.wait_for_timeout(200)
    assert frame.locator("#rd-point option").count() == count
    expect(frame.locator("#rd-json")).to_be_disabled()
    frame.locator("#rd-pause").click()
    expect(frame.locator("#rd-status")).to_contain_text("Complete")
    default = export(page, prefix + "-default")
    assert abs(default["fits"]["ideal"]["measured"]["phase"] - 0.7) < 0.03
    frame.locator("#rd-point").select_option("3")
    frame.locator("#rd-arm").select_option("direct")
    expect(frame.locator("#rd-count-note")).to_contain_text("Direct counting · α=1.571")
    frame.locator("#rd-arm").select_option("finite")
    expect(frame.locator("#rd-count-note")).to_contain_text("Finite π/2 pulse")
    with page.expect_download() as event:
        frame.locator("#rd-csv").click()
    csv = OUT / f"{prefix}-default.csv"
    event.value.save_as(csv)
    assert len(csv.read_text(encoding="utf8").splitlines()) == 37
    heights = {}
    for width in (1440, 390, 320):
        page.set_viewport_size(dict(width=width, height=1000))
        page.wait_for_timeout(250)
        dims = frame.locator("body").evaluate(
            "e=>({width:e.scrollWidth,view:innerWidth,height:e.scrollHeight})"
        )
        assert dims["width"] <= dims["view"], dims
        heights[width] = dims["height"]
        assert dims["height"] < 40000
        actual = page.locator("#quantum-frame").evaluate("e=>e.clientHeight")
        assert actual >= dims["height"] - 2
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.add_style_tag(content=".app-header,.skip-link { visibility: hidden !important; }")
        frame.locator("#readout-lab").screenshot(path=str(OUT / f"{prefix}-{width}.png"))
    page.set_viewport_size(dict(width=1440, height=1000))
    page.add_style_tag(content=".app-header,.skip-link { visibility: visible !important; }")
    assert export(page, prefix + "-manual-after", "tm-json") == manual
    for name, data in earlier.items():
        assert export(page, prefix + f"-{name}-after", f"{name}-json") == data
    page.locator(".wordmark").click()
    page.get_by_role("link", name="Open quantum experiment").click()
    assert export(page, prefix + "-navigation") == default
    assert len(page.context.pages) == 1
    run(frame)
    assert export(page, prefix + "-repeat") == default
    frame.locator("#rd-seed").fill("18")
    run(frame)
    changed = export(page, prefix + "-seed")
    assert (
        changed["records"][0]["arms"]["ideal"]["measurement"]
        != default["records"][0]["arms"]["ideal"]["measurement"]
    )
    frame.locator("#rd-points").fill("3")
    frame.locator("#rd-run").click()
    expect(frame.locator("#rd-status")).to_contain_text("points must")
    assert export(page, prefix + "-invalid-preserved") == changed
    frame.locator("#rd-detuned").click()
    run(frame)
    detuned = export(page, prefix + "-detuned")
    assert abs(detuned["fits"]["finite"]["model"]["phase"] - 0.7) > 0.1
    frame.locator("#rd-fock").click()
    run(frame)
    fock = export(page, prefix + "-fock")
    assert fock["source"]["phase"] is None
    expect(frame.locator("#rd-truth")).to_contain_text("Unavailable")
    frame.locator("#rd-coherent").click()
    frame.locator("#rd-interaction_hz").fill("0.3")
    frame.locator("#rd-hold_ms").fill("150")
    frame.locator("#rd-bias_hz").fill("3")
    frame.get_by_text("Preparation and echo", exact=True).click()
    frame.locator("#rd-echo").select_option("true")
    frame.locator("#rd-initial").select_option("gaussian")
    run(frame)
    export(page, prefix + "-interacting-echo")
    frame.locator("#rd-points").fill("32")
    frame.locator("#rd-run").click()
    expect(frame.locator("#rd-status")).to_contain_text("settings completed")
    frame.locator("#rd-pause").click()
    frame.locator("#rd-cancel").click()
    expect(frame.locator("#rd-status")).to_contain_text("Cancelled")
    partial = export(page, prefix + "-cancelled")
    assert 0 < len(partial["records"]) < 32 and partial["fits"] is None
    expect(frame.locator("#rd-fit")).to_contain_text("Pending full scan")
    assert not errors, errors
    page.close()
    return dict(heights=heights, page_errors=errors, ideal_fit=default["fits"]["ideal"]["measured"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        with serve() as url:
            local = exercise(browser, url, "local")
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as archive:
                archive.extractall(tmp)
            with serve(tmp) as url:
                static = exercise(browser, url, "static")
        browser.close()
    (OUT / "browser.json").write_text(
        json.dumps(dict(local=local, static=static), indent=2), encoding="utf8"
    )
    print("Readout local/static controls, count exports/replay, isolation and mobile passed.")


if __name__ == "__main__":
    main()
