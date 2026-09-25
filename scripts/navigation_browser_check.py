"""Verify same-tab experiment entry and logo-to-library navigation in both builds."""

import tempfile
from pathlib import Path
from zipfile import ZipFile

from playwright.sync_api import expect, sync_playwright

from scripts.twomode_browser_check import serve


def check(browser, base, static=False):
    context = browser.new_context(viewport={"width": 1360, "height": 900})
    page = context.new_page()
    page.goto(base + "/#experiments", wait_until="networkidle")
    expect(page.get_by_role("heading", name="Experiments", exact=True)).to_be_visible()
    page.get_by_role("link", name="Open quantum experiment").click()
    expect(page.locator("#tm-status")).to_contain_text("Ready", timeout=3000)
    assert len(context.pages) == 1, "Experiment 05 opened another tab."
    page.locator(".tm-header a").first.click()
    expect(page.get_by_role("heading", name="Experiments", exact=True)).to_be_visible()
    assert len(context.pages) == 1
    page.get_by_role("link", name="Open 3D experiment").click()
    expect(page.locator("#lab3d-page")).to_be_visible()
    page.locator(".wordmark").click()
    expect(page.get_by_role("heading", name="Experiments", exact=True)).to_be_visible()
    # Direct standalone 04 must also return to the correct local/static library.
    page.goto(base + "/gpu.html", wait_until="networkidle")
    page.locator(".wordmark").click()
    expect(page.get_by_role("heading", name="Experiments", exact=True)).to_be_visible()
    page.goto(base + "/gpu.html", wait_until="networkidle")
    page.get_by_role("link", name="Quantum coherence lab").click()
    expect(page.locator("#tm-status")).to_contain_text("Ready")
    assert len(context.pages) == 1
    page.get_by_role("link", name="Open 3D lab", exact=False).click()
    expect(page.locator("#lab3d-page")).to_be_visible()
    assert len(context.pages) == 1
    if static:
        page.locator(".wordmark").click()
        for width in (1360, 390, 320):
            page.set_viewport_size({"width": width, "height": 900})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=f"artifacts/browser-home-{width}.png", full_page=True)
    context.close()


def main():
    Path("artifacts").mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        with serve() as url:
            check(browser, url)
        with tempfile.TemporaryDirectory() as tmp:
            with ZipFile("artifacts/coldatomlab-webgpu.zip") as archive:
                archive.extractall(tmp)
            with serve(tmp) as url:
                check(browser, url, static=True)
        browser.close()
    print("Local and extracted-static same-tab navigation and home links passed.")


if __name__ == "__main__":
    main()
