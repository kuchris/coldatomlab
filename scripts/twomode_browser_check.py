"""Exercise actual quantum-lab controls and replay exports on local and static servers."""

import contextlib
import functools
import json
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from coldatomlab.replay import verify_export
from coldatomlab.server import LabServer

OUT = Path("artifacts/twomode")


@contextlib.contextmanager
def serve(directory=None):
    if directory is None:
        server = LabServer(("127.0.0.1", 0))
    else:
        handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def capture(page, name):
    with page.expect_download() as event:
        page.locator("#tm-json").click()
    path = OUT / f"{name}.json"
    event.value.save_as(path)
    data = json.loads(path.read_text(encoding="utf8"))
    result = verify_export(data)
    (OUT / f"{name}-replay.json").write_text(json.dumps(result, indent=2), encoding="utf8")
    return data


def complete(page):
    page.locator("#tm-run").click()
    expect(page.locator("#tm-status")).to_contain_text("Complete", timeout=20000)


def recipe(page, name):
    page.locator(f'[data-preset="{name}"]').click()
    page.get_by_role("button", name="Prepare experiment", exact=True).click()
    expect(page.locator("#tm-status")).to_contain_text("Ready")


def exercise(browser, url, prefix):
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    errors, requests = [], []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append(r.url))
    page.goto(url + "/quantum.html", wait_until="networkidle")
    expect(page.locator("#tm-status")).to_contain_text("Ready")
    assert page.locator("#tm-coherence").inner_text() == "0.000"
    page.locator("#tm-run").click()
    page.wait_for_function("parseFloat(document.getElementById('tm-time').textContent)>4")
    page.get_by_role("button", name="Pause", exact=True).click()
    time = page.locator("#tm-time").inner_text()
    page.wait_for_timeout(150)
    assert page.locator("#tm-time").inner_text() == time
    page.locator("#tm-step").click()
    assert page.locator("#tm-time").inner_text() != time
    page.locator("#tm-sample").click()
    measured = capture(page, prefix + "-paused")
    page.locator("#tm-sample").click()
    repeated = capture(page, prefix + "-repeat")
    assert repeated == measured
    page.locator("#tm-seed").fill("18")
    page.locator("#tm-sample").click()
    changed = capture(page, prefix + "-new-seed")
    assert changed["current"]["state"] == measured["current"]["state"]
    assert (
        changed["current"]["measurement"]["counts"] != measured["current"]["measurement"]["counts"]
    )
    page.locator("#tm-shots").fill("0")
    page.locator("#tm-sample").click()
    expect(page.locator("#tm-status")).to_have_class("error")
    page.locator("#tm-shots").fill("1000")
    page.locator("#tm-atoms").fill("2.5")
    page.get_by_role("button", name="Prepare experiment", exact=True).click()
    assert not page.locator("#tm-atoms").evaluate("e=>e.checkValidity()")
    assert capture(page, prefix + "-invalid")["current"]["config"]["atoms"] == 40
    # Reset preserves the applied run while edited controls remain pending.
    page.locator("#tm-reset").click()
    assert page.locator("#tm-left").inner_text() == "40.00"
    expect(page.locator("#tm-status")).to_contain_text("pending")
    recipe(page, "tunnelling")
    complete(page)
    assert page.locator("#tm-left").inner_text() == "40.00"
    capture(page, prefix + "-tunnelling")
    recipe(page, "diffusion")
    complete(page)
    page.locator("#tm-sample").click()
    coherent = capture(page, prefix + "-coherent")
    page.locator("#tm-pin").click()
    recipe(page, "narrow")
    complete(page)
    page.locator("#tm-sample").click()
    comparison = capture(page, prefix + "-comparison")
    assert comparison["pinned"] == coherent["current"]
    assert (
        comparison["current"]["state"]["variance_left"]
        < comparison["pinned"]["state"]["variance_left"]
    )
    with page.expect_download() as event:
        page.locator("#tm-csv").click()
    path = OUT / f"{prefix}-history.csv"
    event.value.save_as(path)
    lines = path.read_text().splitlines()
    assert len(lines) == 403 and "interaction_hz" in lines[0]
    page.evaluate("window.scrollTo(0,0)")
    page.screenshot(path=str(OUT / f"{prefix}-desktop.png"), full_page=True)
    for width in [390, 320]:
        page.set_viewport_size({"width": width, "height": 844})
        page.wait_for_timeout(100)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), width
        assert page.locator("#tm-distribution svg").bounding_box()["width"] >= 250
        page.screenshot(path=str(OUT / f"{prefix}-mobile-{width}.png"), full_page=True)
    page.set_viewport_size({"width": 1440, "height": 1000})
    page.locator("#tm-clear").click()
    expect(page.locator("#tm-reference")).to_contain_text("No pinned reference")
    recipe(page, "fock")
    assert page.locator("#tm-phase-value").inner_text() == "Unavailable"
    page.locator("#tm-sample").click()
    fock = capture(page, prefix + "-fock")
    assert fock["current"]["measurement"]["counts"][20] == 1000
    # The solver remains responsive at the largest supported basis.
    page.locator("#tm-atoms").fill("100")
    page.locator("#tm-tunnelling_hz").fill("20")
    page.locator("#tm-interaction_hz").fill("2")
    page.get_by_role("button", name="Prepare experiment", exact=True).click()
    page.locator("#tm-step").click()
    capture(page, prefix + "-large")
    assert not errors, errors
    assert not any("/api/" in r for r in requests), requests
    page.close()
    return {
        "page_errors": errors,
        "simulation_api_requests": 0,
        "responsive_widths": [1440, 390, 320],
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        with serve() as url:
            integrated = exercise(browser, url, "integrated")
            page = browser.new_page()
            page.goto(url, wait_until="networkidle")
            expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
            frozen = page.evaluate("JSON.stringify({session,state,reference})")
            page.locator("#experiment-search").fill("quantum")
            expect(page.locator("#library-count")).to_have_text("1 experiment")
            with page.expect_popup() as popup:
                page.get_by_role("link", name="Open quantum experiment").click()
            popup.value.wait_for_load_state("networkidle")
            expect(popup.value.locator("#tm-status")).to_contain_text("Ready")
            popup.value.close()
            assert page.url == url + "/"
            assert page.evaluate("JSON.stringify({session,state,reference})") == frozen
            page.close()
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as archive:
                archive.extractall(tmp)
            with serve(tmp) as url:
                static = exercise(browser, url, "static")
                page = browser.new_page()
                page.goto(url + "/gpu.html", wait_until="networkidle")
                with page.expect_popup() as popup:
                    page.get_by_role("link", name="Quantum coherence lab").click()
                expect(popup.value.locator("#tm-status")).to_contain_text("Ready")
                popup.value.close()
                page.close()
        browser.close()
    (OUT / "browser.json").write_text(
        json.dumps({"integrated": integrated, "static": static}, indent=2), encoding="utf8"
    )
    print(
        "Two-mode browser controls, independent replay, mobile and extracted static package passed."
    )


if __name__ == "__main__":
    main()
