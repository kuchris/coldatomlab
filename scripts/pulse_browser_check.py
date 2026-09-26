"""Exercise finite pulses on local and static hosts; replay actual browser exports."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/pulse")


def export(page, label, button="fp-json"):
    with page.expect_download() as event:
        page.frame_locator("#quantum-frame").locator(f"#{button}").click()
    path = OUT / f"{label}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    result = verify_export(data)
    (OUT / f"{label}-replay.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    return data


def run(frame):
    frame.locator("#fp-run").click()
    expect(frame.locator("#fp-status")).to_contain_text("Complete", timeout=60000)


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
    frame.locator("#tm-step").click()
    frame.locator("#tm-pin").click()
    manual = export(page, prefix + "-manual-before", "tm-json")
    frame.locator("#ep-count").fill("2")
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("Complete")
    prep = export(page, prefix + "-prep-before", "ep-json")
    frame.locator("#se-preparations").fill("2")
    frame.locator("#se-run").click()
    expect(frame.locator("#se-status")).to_contain_text("Complete")
    echo = export(page, prefix + "-echo-before", "se-json")
    frame.get_by_role("button", name="Finite pulse comparison ↓", exact=True).click()
    assert page.url.endswith("/#quantum") and len(page.context.pages) == 1
    frame.locator("#fp-run").click()
    expect(frame.locator("#fp-status")).to_contain_text("five-arm preparations completed")
    frame.locator("#fp-pause").click()
    expect(frame.locator("#fp-status")).to_contain_text("Paused")
    applied = frame.locator("#fp-applied").inner_text()
    page.wait_for_timeout(200)
    assert frame.locator("#fp-applied").inner_text() == applied
    expect(frame.locator("#fp-json")).to_be_disabled()
    frame.locator("#fp-pause").click()
    expect(frame.locator("#fp-status")).to_contain_text("Complete", timeout=60000)
    default = export(page, prefix + "-default")
    expect(frame.locator("#fp-zoom")).to_be_checked()
    assert "229" in frame.locator("#fp-population").inner_text()
    frame.locator("#fp-zoom").uncheck()
    assert "500" in frame.locator("#fp-population").inner_text()
    frame.locator("#fp-zoom").check()
    assert len(default["records"]) == 32
    assert abs(default["aggregate"]["ideal"]["history"][-1]["ensemble_coherence"] - 1) < 1e-12
    assert export(page, prefix + "-manual-after", "tm-json") == manual
    assert export(page, prefix + "-prep-after", "ep-json") == prep
    assert export(page, prefix + "-echo-after", "se-json") == echo
    frame.locator("#fp-on").click()
    expect(frame.locator("#fp-stage-note")).to_contain_text("pulse active · applied J = 10 Hz")
    frame.locator("#fp-off").click()
    expect(frame.locator("#fp-stage-note")).to_contain_text("second hold · applied J = 0 Hz")
    frame.locator("#fp-arm").select_option("short")
    frame.locator("#fp-on").click()
    expect(frame.locator("#fp-time")).to_contain_text("240 ms")
    frame.locator("#fp-arm").select_option("long")
    frame.locator("#fp-on").click()
    expect(frame.locator("#fp-time")).to_contain_text("235 ms")
    selected = frame.locator("#fp-selected").inner_text()
    frame.locator("#fp-member").fill("2")
    assert frame.locator("#fp-selected").inner_text() != selected
    frame.locator("#fp-start").click()
    frame.locator("#fp-play").click()
    page.wait_for_function(
        "+document.getElementById('quantum-frame').contentDocument.getElementById('fp-slider').value > 2"
    )
    frame.locator("#fp-play").click()
    step = frame.locator("#fp-slider").input_value()
    page.wait_for_timeout(200)
    assert frame.locator("#fp-slider").input_value() == step
    last = len(default["checkpoints"]) - 1
    frame.locator("#fp-slider").fill(str(last - 1))
    frame.locator("#fp-play").click()
    expect(frame.locator("#fp-play")).to_have_text("Play pulse timeline")
    assert frame.locator("#fp-slider").input_value() == str(last)
    assert export(page, prefix + "-playback") == default
    page.locator(".wordmark").click()
    page.get_by_role("link", name="Open quantum experiment").click()
    assert export(page, prefix + "-navigation") == default
    run(frame)
    assert export(page, prefix + "-repeat") == default
    heights = {}
    for width in (1440, 390, 320):
        page.set_viewport_size({"width": width, "height": 1000})
        page.wait_for_timeout(200)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert frame.locator("body").evaluate("e=>e.scrollWidth <= innerWidth")
        heights[width] = frame.locator("body").evaluate(
            "() => document.documentElement.scrollHeight"
        )
        assert heights[width] < 20000, heights
        style = page.add_style_tag(content=".app-header,.skip-link{visibility:hidden!important}")
        frame.locator("#pulse-lab").screenshot(path=str(OUT / f"{prefix}-{width}.png"))
        style.evaluate("e=>e.remove()")
    page.set_viewport_size({"width": 1440, "height": 1000})
    with page.expect_download() as event:
        frame.locator("#fp-csv").click()
    path = OUT / f"{prefix}-history.csv"
    event.value.save_as(path)
    rows = path.read_text().splitlines()
    assert len(rows) == 1 + 5 * len(default["checkpoints"]) and "active_j_hz" in rows[0]
    frame.locator("#fp-duration_ms").fill("30")
    frame.locator("#fp-run").click()
    expect(frame.locator("#fp-status")).to_contain_text("longest pulse must be shorter")
    assert export(page, prefix + "-invalid-preserved") == default
    frame.locator("#fp-transfer").click()
    frame.locator("#fp-preparations").fill("4")
    run(frame)
    transfer = export(page, prefix + "-transfer")
    assert transfer["plan"]["base"]["left_fraction"] == 1
    assert transfer["aggregate"]["nominal"]["history"][-1]["mean_left"] < 1e-10
    assert (
        abs(transfer["aggregate"]["short"]["history"][-1]["mean_left"] / 40 - 0.0954915028) < 1e-9
    )
    frame.locator("#fp-arm").select_option("nominal")
    frame.locator("#fp-middle").click()
    expect(frame.locator("#fp-selected")).to_contain_text("⟨NL⟩=20.000")
    expect(frame.locator("#fp-stage-note")).to_contain_text("pulse active")
    frame.locator("#fp-end").click()
    expect(frame.locator("#fp-selected")).to_contain_text("Unavailable")
    frame.locator("#fp-error").fill("0")
    run(frame)
    zero = export(page, prefix + "-zero-error")
    assert zero["records"][0]["arms"]["short"] == zero["records"][0]["arms"]["long"]
    frame.locator("#fp-interacting").click()
    run(frame)
    interacting = export(page, prefix + "-interacting")
    assert interacting["plan"]["base"]["interaction_hz"] == 0.3
    frame.locator("#fp-seed").fill("18")
    run(frame)
    changed = export(page, prefix + "-changed-seed")
    assert changed["records"][0]["bias_offset_hz"] != interacting["records"][0]["bias_offset_hz"]
    frame.locator("#fp-preparations").fill("128")
    frame.locator("#fp-run").click()
    expect(frame.locator("#fp-status")).to_contain_text("five-arm preparations completed")
    frame.locator("#fp-pause").click()
    frame.locator("#fp-cancel").click()
    expect(frame.locator("#fp-status")).to_contain_text("Cancelled")
    partial = export(page, prefix + "-cancelled")
    assert partial["status"] == "cancelled" and 0 < len(partial["records"]) < 128
    assert not errors, errors
    assert not api, api
    page.close()
    return dict(
        page_errors=errors,
        quantum_api_requests=api,
        heights=heights,
        final={
            arm: dict(
                coherence=default["aggregate"][arm]["history"][-1]["ensemble_coherence"],
                fidelity=default["aggregate"][arm]["mean_fidelity_to_ideal"],
            )
            for arm in default["aggregate"]
        },
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
        "Finite pulse local/static controls, live timeline, exports/replay, isolation and mobile passed."
    )


if __name__ == "__main__":
    main()
