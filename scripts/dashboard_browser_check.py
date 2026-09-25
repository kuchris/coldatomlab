"""Verify library navigation against the real solver, including mobile layouts."""

import argparse
import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    out = Path("artifacts")
    out.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1000})
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(args.url)
        page.wait_for_load_state("networkidle")
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#experiment-library")).to_be_visible()
        expect(page.locator("#lab-workbench")).to_be_hidden()
        expect(page.locator(".experiment-card:visible")).to_have_count(5)
        page.screenshot(path=str(out / "dashboard-desktop.png"), full_page=True)
        search = page.get_by_role("searchbox", name="Search experiments")
        search.fill("phase")
        expect(page.locator(".experiment-card:visible")).to_have_count(2)
        search.fill("no such experiment")
        expect(page.locator("#library-empty")).to_be_visible()
        page.get_by_role("button", name="Clear search", exact=True).click()
        expect(page.locator(".experiment-card:visible")).to_have_count(5)
        page.get_by_role("button", name="List view", exact=True).click()
        expect(page.locator("#experiment-cards")).to_have_class("experiment-cards list-layout")
        page.screenshot(path=str(out / "dashboard-list.png"), full_page=True)
        page.get_by_role("button", name="Grid view", exact=True).click()
        page.locator("#library-model").click()
        expect(page.locator("#model-dialog")).to_be_visible()
        page.keyboard.press("Escape")

        for kind in ("single", "sequence"):
            page.locator(f'[data-experiment="{kind}"]').click()
            expect(page.locator("#experiment")).to_have_value(kind)
            page.locator('[data-route="experiments"]').click()

        initial_session = page.evaluate("session")
        initial_steps = page.evaluate("state.diagnostics.steps")
        page.get_by_role("button", name="Set up interference").click()
        expect(page.locator("#lab-workbench")).to_be_visible()
        expect(page.locator("#experiment")).to_have_value("double")
        expect(page.locator("#status")).to_have_text("Parameters changed")
        assert page.evaluate("session") == initial_session
        assert page.evaluate("state.diagnostics.steps") == initial_steps
        # Choosing a card stages settings; only Prepare changes the numerical state.
        page.locator("#prepare").click()
        expect(page.locator("#status")).to_have_text("Ready", timeout=30000)
        expect(page.locator("#experiment-title")).to_have_text("Matter-wave interference")
        page.locator("#step").click()
        expect(page.locator("#status")).to_have_text("Paused")
        page.locator("#pin").click()
        expect(page.locator("#comparison")).to_be_visible()
        frozen = page.evaluate("JSON.stringify({session, state, reference})")
        page.locator('[data-route="experiments"]').click()
        expect(page.locator("#library-session-status")).to_contain_text("Paused")
        page.locator('[data-route="measurements"]').click()
        expect(page.locator("#measurements")).to_be_in_viewport()
        assert page.evaluate("JSON.stringify({session, state, reference})") == frozen
        page.locator('[data-route="camera-lab"]').click()
        expect(page.locator("#camera-lab")).to_be_in_viewport()
        expect(page.locator("#capture")).to_be_disabled()
        page.go_back()
        expect(page.locator('[data-route="measurements"]')).to_have_attribute(
            "aria-current", "page"
        )
        page.locator('[data-route="workspace"]').click()
        page.screenshot(path=str(out / "dashboard-workspace.png"), full_page=True)
        page.locator("#run").click()
        page.locator('[data-route="experiments"]').click()
        expect(page.locator("#library-session-status")).to_contain_text("Running")
        for button in page.locator(".open-experiment").all():
            expect(button).to_be_disabled()
        page.locator('[data-route="workspace"]').click()
        page.locator("#run").click()
        expect(page.locator("#status")).to_have_text("Paused")

        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 850})
            page.locator("#nav-toggle").click()
            expect(page.locator("#lab-navigation")).to_be_visible()
            page.locator('[data-route="experiments"]').click()
            expect(page.locator("#lab-navigation")).to_be_hidden()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(out / f"dashboard-mobile-{width}.png"), full_page=True)
            page.locator("#nav-toggle").click()
            page.keyboard.press("Escape")
            expect(page.locator("#nav-toggle")).to_be_focused()
            expect(page.locator("#lab-navigation")).to_be_hidden()
            page.locator("#nav-toggle").click()
            page.locator('[data-route="workspace"]').click()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.locator("#nav-toggle").click()
            page.locator('[data-route="workspace"]').click()
            expect(page.locator("#lab-navigation")).to_be_hidden()
        assert not errors, errors
        (out / "dashboard-browser-report.json").write_text(
            json.dumps(
                {
                    "search_and_layout": True,
                    "staged_card_settings": True,
                    "navigation_preserves_state_and_reference": True,
                    "running_state_guard": True,
                    "history_navigation": True,
                    "mobile_widths": [390, 320],
                    "page_errors": errors,
                },
                indent=2,
            )
        )
        browser.close()
    print("Dashboard browser checks passed.")


if __name__ == "__main__":
    main()
