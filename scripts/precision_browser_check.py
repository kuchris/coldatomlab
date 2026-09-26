"""Exercise repeated scan precision on local and extracted-static browser hosts."""

import json
import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from scripts.twomode_browser_check import serve

OUT = Path("artifacts/precision")


def export(page, name, button="pb-json"):
    with page.expect_download() as event:
        page.frame_locator("#quantum-frame").locator(f"#{button}").click()
    path = OUT / f"{name}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    check = verify_export(data)
    (OUT / f"{name}-replay.json").write_text(json.dumps(check, indent=2), encoding="utf8")
    return data


def run(frame):
    frame.locator("#pb-run").click()
    expect(frame.locator("#pb-status")).to_contain_text("Complete", timeout=120000)


def exercise(browser, url, prefix):
    page = browser.new_page(viewport=dict(width=1440, height=1000), accept_downloads=True)
    errors, api = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on(
        "request",
        lambda r: api.append(r.url) if "quantum.html" in r.frame.url and "/api" in r.url else None,
    )
    page.goto(url + "/#quantum", wait_until="networkidle")
    frame = page.frame_locator("#quantum-frame")
    expect(frame.locator("#tm-status")).to_contain_text("Ready", timeout=30000)
    frame.locator("#tm-step").click()
    frame.locator("#tm-pin").click()
    old = {"tm": export(page, prefix + "-tm-before", "tm-json")}
    for name, count in [
        ("ep", "count"),
        ("se", "preparations"),
        ("fp", "preparations"),
        ("rd", None),
    ]:
        if count:
            frame.locator(f"#{name}-{count}").fill("2")
        frame.locator(f"#{name}-run").click()
        expect(frame.locator(f"#{name}-status")).to_contain_text("Complete", timeout=60000)
        old[name] = export(page, prefix + f"-{name}-before", f"{name}-json")
    frame.get_by_role("button", name="Precision benchmark ↓", exact=True).click()
    assert page.url.endswith("/#quantum") and len(page.context.pages) == 1
    frame.locator("#pb-run").click()
    expect(frame.locator("#pb-status")).to_contain_text(
        "full-scan repetitions completed", timeout=60000
    )
    frame.locator("#pb-pause").click()
    expect(frame.locator("#pb-status")).to_contain_text("Paused")
    applied = frame.locator("#pb-applied").inner_text()
    page.wait_for_timeout(250)
    assert frame.locator("#pb-applied").inner_text() == applied
    expect(frame.locator("#pb-json")).to_be_disabled()
    frame.locator("#pb-pause").click()
    expect(frame.locator("#pb-status")).to_contain_text("Complete", timeout=120000)
    default = export(page, prefix + "-default")
    assert len(default["records"]) == 100
    s = default["summary"]
    assert (
        s["more_atoms"]["ideal"]["circular_scatter"]
        < 0.7 * s["baseline"]["ideal"]["circular_scatter"]
    )
    assert (
        s["more_shots"]["ideal"]["circular_scatter"]
        < 0.7 * s["baseline"]["ideal"]["circular_scatter"]
    )
    for name in ("more_atoms", "more_shots", "baseline"):
        frame.locator("#pb-case").select_option(name)
        expect(frame.locator("#pb-hist-note")).to_contain_text("true phase=0.7000")
    with page.expect_download() as event:
        frame.locator("#pb-csv").click()
    csv = OUT / f"{prefix}-default.csv"
    event.value.save_as(csv)
    assert len(csv.read_text(encoding="utf8").splitlines()) == 601
    heights = {}
    for width in (1440, 390, 320):
        page.set_viewport_size(dict(width=width, height=1000))
        page.wait_for_timeout(250)
        dims = frame.locator("body").evaluate(
            "e=>({width:e.scrollWidth,view:innerWidth,height:e.scrollHeight})"
        )
        assert dims["width"] <= dims["view"], dims
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("#quantum-frame").evaluate("e=>e.clientHeight") >= dims["height"] - 2
        assert dims["height"] < 40000
        heights[width] = dims["height"]
        page.add_style_tag(content=".app-header,.skip-link {visibility:hidden!important}")
        frame.locator("#precision-lab").screenshot(path=str(OUT / f"{prefix}-{width}.png"))
    page.set_viewport_size(dict(width=1440, height=1000))
    page.add_style_tag(content=".app-header,.skip-link {visibility:visible!important}")
    for name, data in old.items():
        assert export(page, prefix + f"-{name}-after", f"{name}-json") == data
    page.locator(".wordmark").click()
    page.get_by_role("link", name="Open quantum experiment").click()
    assert export(page, prefix + "-navigation") == default
    run(frame)
    assert export(page, prefix + "-repeat") == default
    frame.locator("#pb-seed").fill("18")
    run(frame)
    changed = export(page, prefix + "-seed")
    assert changed["records"] != default["records"]
    frame.locator("#pb-more_atoms").fill("20")
    frame.locator("#pb-run").click()
    expect(frame.locator("#pb-status")).to_contain_text("more_atoms must")
    assert export(page, prefix + "-invalid-preserved") == changed
    frame.locator("#pb-biased").click()
    run(frame)
    biased = export(page, prefix + "-biased")
    assert abs(biased["summary"]["baseline"]["finite"]["circular_bias"]) > 0.4
    frame.locator("#precision-lab").screenshot(path=str(OUT / f"{prefix}-biased.png"))
    frame.locator("#pb-dark").click()
    frame.locator("#pb-repetitions").fill("20")
    run(frame)
    dark = export(page, prefix + "-dark")
    assert dark["summary"]["baseline"]["ideal"]["circular_bias"] is None
    expect(frame.locator("#pb-hist-note")).to_contain_text("No identifiable")
    frame.locator("#pb-calibrated").click()
    frame.locator("#pb-repetitions").fill("300")
    frame.locator("#pb-points").fill("32")
    frame.locator("#pb-shots").fill("4000")
    frame.locator("#pb-more_shots").fill("4096")
    frame.locator("#pb-run").click()
    expect(frame.locator("#pb-status")).to_contain_text("16 million")
    frame.locator("#pb-calibrated").click()
    frame.get_by_text("Initial state and hold", exact=True).click()
    frame.locator("#pb-interaction_hz").fill("0.3")
    frame.locator("#pb-hold_ms").fill("150")
    frame.locator("#pb-echo").select_option("true")
    frame.locator("#pb-run").click()
    expect(frame.locator("#pb-status")).to_contain_text(
        "full-scan repetitions completed", timeout=60000
    )
    frame.locator("#pb-pause").click()
    frame.locator("#pb-cancel").click()
    expect(frame.locator("#pb-status")).to_contain_text("Cancelled")
    partial = export(page, prefix + "-cancelled-interacting")
    assert 0 < len(partial["records"]) < 300
    assert partial["models"][0]["ideal_scatter_guide"] is None
    assert not errors, errors
    assert not api, api
    page.close()
    return dict(
        heights=heights, page_errors=errors, quantum_api_requests=api, summary=default["summary"]
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        with serve() as url:
            local = exercise(browser, url, "local")
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as z:
                z.extractall(tmp)
            with serve(tmp) as url:
                static = exercise(browser, url, "static")
        browser.close()
    (OUT / "browser.json").write_text(
        json.dumps(dict(local=local, static=static), indent=2), encoding="utf8"
    )
    print(
        "Precision local/static repeated counts, controls, exports/replay, isolation and mobile passed."
    )


if __name__ == "__main__":
    main()
