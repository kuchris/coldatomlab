"""Run preparation ensembles through real controls in both local and static dashboards."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/preparation")


def export(page, prefix, manual=False):
    frame = page.frame_locator("#quantum-frame")
    with page.expect_download() as event:
        frame.locator("#tm-json" if manual else "#ep-json").click()
    path = OUT / f"{prefix}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    check = verify_export(data)
    (OUT / f"{prefix}-replay.json").write_text(json.dumps(check, indent=2), encoding="utf8")
    return data


def run(frame):
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("Complete", timeout=30000)


def check(browser, base, prefix):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors, api = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "request",
        lambda r: api.append(r.url) if "quantum.html" in r.frame.url and "/api" in r.url else None,
    )
    page.goto(base + "/#quantum", wait_until="networkidle")
    frame = page.frame_locator("#quantum-frame")
    expect(frame.locator("#tm-status")).to_contain_text("Ready")
    frame.locator("#tm-step").click()
    frame.locator("#tm-pin").click()
    before = export(page, prefix + "-manual-before", manual=True)
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("preparations completed", timeout=10000)
    frame.locator("#ep-pause").click()
    expect(frame.locator("#ep-status")).to_contain_text("Paused")
    count = frame.locator("#ep-rows tr").count()
    page.wait_for_timeout(200)
    assert frame.locator("#ep-rows tr").count() == count
    expect(frame.locator("#ep-json")).to_be_disabled()
    frame.locator("#ep-pause").click()
    expect(frame.locator("#ep-status")).to_contain_text("Complete", timeout=30000)
    default = export(page, prefix + "-default")
    assert default["aggregate"]["history"][-1]["mean_individual_coherence"] > 0.999999
    assert default["aggregate"]["history"][-1]["ensemble_coherence"] < 0.25
    assert export(page, prefix + "-manual-after", manual=True) == before
    run(frame)
    assert export(page, prefix + "-repeat") == default
    # Navigating away preserves the ensemble rather than silently preparing again.
    page.locator(".wordmark").click()
    page.get_by_role("link", name="Open quantum experiment").click()
    assert export(page, prefix + "-navigation") == default
    for width in (1440, 390, 320):
        page.set_viewport_size({"width": width, "height": 1000})
        page.wait_for_timeout(150)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert frame.locator("body").evaluate("e=>e.scrollWidth <= innerWidth")
        frame.locator("#ensemble-lab").screenshot(path=str(OUT / f"{prefix}-{width}.png"))
    page.set_viewport_size({"width": 1440, "height": 1000})
    with page.expect_download() as event:
        frame.locator("#ep-csv").click()
    csv = OUT / f"{prefix}-history.csv"
    event.value.save_as(csv)
    lines = csv.read_text().splitlines()
    assert len(lines) == 102 and "mean_individual_coherence" in lines[0]
    frame.locator("#ep-count").fill("1")
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_have_class("error")
    assert export(page, prefix + "-invalid-preserved") == default
    frame.locator("#ep-count").fill("8")
    frame.locator("#ep-seed").fill("18")
    run(frame)
    changed = export(page, prefix + "-seed")
    assert changed["records"][0]["phase_offset"] != default["records"][0]["phase_offset"]
    frame.locator("#ep-phase").fill("0")
    frame.locator("#ep-bias").fill("0")
    run(frame)
    zero = export(page, prefix + "-zero")
    assert abs(zero["aggregate"]["history"][-1]["ensemble_coherence"] - 1) < 1e-10
    frame.locator("#ep-interacting").click()
    run(frame)
    export(page, prefix + "-interacting")
    # Copy only the prepared manual settings, preserving the manual run itself.
    for key, value in {
        "atoms": 12,
        "left_fraction": 0.5,
        "tunnelling_hz": 2,
        "interaction_hz": 0.3,
        "duration_ms": 150,
    }.items():
        frame.locator(f"#tm-{key}").fill(str(value))
    frame.get_by_role("button", name="Prepare experiment", exact=True).click()
    frame.locator("#tm-atoms").fill("20")  # pending edit must not leak into ensemble
    frame.locator("#ep-copy").click()
    expect(frame.locator("#ep-base")).to_contain_text("N=12")
    run(frame)
    coupled = export(page, prefix + "-coupled")
    assert coupled["plan"]["base"]["atoms"] == 12
    assert coupled["aggregate"]["history"][-1]["guide_coherence"] is None
    assert coupled["aggregate"]["history"][-1]["between_variance"] > 0
    frame.locator("#ep-count").fill("128")
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("preparations completed")
    frame.locator("#ep-pause").click()
    frame.locator("#ep-cancel").click()
    expect(frame.locator("#ep-status")).to_contain_text("Cancelled")
    partial = export(page, prefix + "-cancelled")
    assert 0 < len(partial["records"]) < 128
    assert partial["status"] == "cancelled"
    # An invalid bias range is rejected without silently clipping realizations.
    frame.locator("#tm-bias_hz").fill("20")
    frame.get_by_role("button", name="Prepare experiment", exact=True).click()
    frame.locator("#ep-copy").click()
    frame.locator("#ep-run").click()
    expect(frame.locator("#ep-status")).to_contain_text("no samples are clipped")
    assert export(page, prefix + "-range-preserved") == partial
    assert not errors, errors
    assert not api, api
    page.close()
    return dict(
        page_errors=errors,
        quantum_api_requests=api,
        default_preparations=64,
        default_final=default["aggregate"]["history"][-1],
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        with serve() as url:
            local = check(browser, url, "local")
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as archive:
                archive.extractall(tmp)
            with serve(tmp) as url:
                static = check(browser, url, "static")
        browser.close()
    (OUT / "browser.json").write_text(
        json.dumps(dict(local=local, static=static), indent=2), encoding="utf8"
    )
    print(
        "Preparation ensembles: local/static controls, independent replay, manual isolation and mobile passed."
    )


if __name__ == "__main__":
    main()
