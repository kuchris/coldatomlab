"""Verify paired echo controls, time inspection and full exports on local/static hosts."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/echo")


def export(page, label, button="se-json"):
    with page.expect_download() as event:
        page.frame_locator("#quantum-frame").locator(f"#{button}").click()
    path = OUT / f"{label}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    result = verify_export(data)
    (OUT / f"{label}-replay.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    return data


def run(frame):
    frame.locator("#se-run").click()
    expect(frame.locator("#se-status")).to_contain_text("Complete", timeout=30000)


def exercise(browser, url, prefix):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors, api = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "request",
        lambda r: api.append(r.url) if "quantum.html" in r.frame.url and "/api" in r.url else None,
    )
    page.goto(url + "/#quantum", wait_until="networkidle")
    frame = page.frame_locator("#quantum-frame")
    expect(frame.locator("#tm-status")).to_contain_text("Ready")
    frame.get_by_role("button", name="Spin echo comparison ↓", exact=True).click()
    assert page.url.endswith("/#quantum") and len(page.context.pages) == 1
    assert page.evaluate("window.scrollY > 0")
    frame.locator("#tm-step").click()
    frame.locator("#tm-pin").click()
    manual = export(page, prefix + "-manual-before", "tm-json")
    frame.locator("#ep-count").fill("4")
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("Complete")
    preparation = export(page, prefix + "-preparation-before", "ep-json")
    frame.locator("#se-run").click()
    expect(frame.locator("#se-status")).to_contain_text("paired preparations completed")
    frame.locator("#se-pause").click()
    expect(frame.locator("#se-status")).to_contain_text("Paused")
    applied = frame.locator("#se-applied").inner_text()
    page.wait_for_timeout(150)
    assert frame.locator("#se-applied").inner_text() == applied
    expect(frame.locator("#se-json")).to_be_disabled()
    frame.locator("#se-pause").click()
    expect(frame.locator("#se-status")).to_contain_text("Complete", timeout=30000)
    default = export(page, prefix + "-default")
    assert abs(default["aggregate"]["echo"]["history"][-1]["ensemble_coherence"] - 1) < 1e-12
    assert default["aggregate"]["no_echo"]["history"][-1]["ensemble_coherence"] < 0.5
    assert export(page, prefix + "-manual-after", "tm-json") == manual
    assert export(page, prefix + "-preparation-after", "ep-json") == preparation
    frame.locator("#se-before").click()
    expect(frame.locator("#se-time")).to_have_text("t = 250 ms · before pulse")
    before = frame.locator("#se-reading-echo").inner_text()
    frame.locator("#se-after").click()
    expect(frame.locator("#se-time")).to_have_text("t = 250 ms · after pulse")
    assert frame.locator("#se-reading-echo").inner_text() != before
    frame.locator("#se-start").click()
    frame.locator("#se-play").click()
    page.wait_for_function(
        "+document.getElementById('quantum-frame').contentDocument.getElementById('se-slider').value > 2"
    )
    frame.locator("#se-play").click()
    stopped = frame.locator("#se-slider").input_value()
    page.wait_for_timeout(200)
    assert frame.locator("#se-slider").input_value() == stopped
    frame.locator("#se-slider").fill("75")
    expect(frame.locator("#se-time")).to_contain_text("370 ms")
    frame.locator("#se-slider").fill("100")
    frame.locator("#se-play").click()
    expect(frame.locator("#se-play")).to_have_text("Play timeline")
    assert frame.locator("#se-slider").input_value() == "101"
    assert export(page, prefix + "-playback") == default
    page.locator(".wordmark").click()
    page.get_by_role("link", name="Open quantum experiment").click()
    assert export(page, prefix + "-navigation") == default
    run(frame)
    assert export(page, prefix + "-repeat") == default
    # Inspect complete layouts including both preceding experiment panels.
    for width in (1440, 390, 320):
        page.set_viewport_size({"width": width, "height": 1000})
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert frame.locator("body").evaluate("e => e.scrollWidth <= innerWidth")
        height = frame.locator("body").evaluate("() => document.documentElement.scrollHeight")
        assert height < 20000, height
        # Exclude the fixed parent navigation from this section-only evidence image.
        overlay_style = page.add_style_tag(
            content=".app-header,.skip-link { visibility: hidden !important; }"
        )
        frame.locator("#echo-lab").screenshot(path=str(OUT / f"{prefix}-{width}.png"))
        overlay_style.evaluate("e=>e.remove()")
    page.set_viewport_size({"width": 1440, "height": 1000})
    with page.expect_download() as event:
        frame.locator("#se-csv").click()
    path = OUT / f"{prefix}-history.csv"
    event.value.save_as(path)
    lines = path.read_text().splitlines()
    assert len(lines) == 205 and "pulse_applied" in lines[0]
    frame.locator("#se-preparations").fill("1")
    frame.locator("#se-run").click()
    expect(frame.locator("#se-status")).to_have_class("error")
    assert export(page, prefix + "-invalid-preserved") == default
    frame.locator("#se-preparations").fill("8")
    frame.locator("#se-seed").fill("18")
    run(frame)
    changed = export(page, prefix + "-seed")
    assert changed["records"][0]["bias_offset_hz"] != default["records"][0]["bias_offset_hz"]
    frame.locator("#se-bias_half_range_hz").fill("0")
    run(frame)
    zero = export(page, prefix + "-zero")
    assert abs(zero["aggregate"]["no_echo"]["history"][-1]["ensemble_coherence"] - 1) < 1e-12
    frame.locator("#se-phase").click()
    run(frame)
    phase = export(page, prefix + "-phase-spread")
    rows = phase["aggregate"]["echo"]["history"]
    assert abs(rows[-1]["ensemble_coherence"] - rows[0]["ensemble_coherence"]) < 1e-12
    assert rows[-1]["ensemble_coherence"] < 0.99
    frame.locator("#se-interacting").click()
    run(frame)
    interacting = export(page, prefix + "-interacting")
    assert interacting["aggregate"]["echo"]["history"][-1]["ensemble_coherence"] < 1e-10
    expect(frame.locator("#se-reading-echo")).to_contain_text("Unavailable")
    expect(frame.locator("#se-explanation")).to_contain_text("does not reverse U")
    frame.locator("#se-preparations").fill("128")
    frame.locator("#se-run").click()
    expect(frame.locator("#se-status")).to_contain_text("paired preparations completed")
    frame.locator("#se-pause").click()
    frame.locator("#se-cancel").click()
    expect(frame.locator("#se-status")).to_contain_text("Cancelled")
    partial = export(page, prefix + "-cancelled")
    assert partial["status"] == "cancelled" and 0 < len(partial["records"]) < 128
    assert not errors, errors
    assert not api, api
    page.close()
    return dict(
        page_errors=errors,
        quantum_api_requests=api,
        final={arm: default["aggregate"][arm]["history"][-1] for arm in ("no_echo", "echo")},
    )


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
    print(
        "Echo local/static controls, timeline, exports/replay, isolation and mobile checks passed."
    )


if __name__ == "__main__":
    main()
