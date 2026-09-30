"""Real Chromium smoke: configure, author persona, launch, view and replay."""

import os
import subprocess
import sys
import time
import urllib.request

import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.mark.browser
def test_frontend_configuration_persona_launch_and_replay(tmp_path):
    env = {**os.environ, "CLOCKTOWER_DATA": str(tmp_path)}
    server = subprocess.Popen(
        [sys.executable, "-m", "clocktower.cli", "web", "--port", "8013"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )
    try:
        for _ in range(100):
            try:
                urllib.request.urlopen("http://127.0.0.1:8013/", timeout=1).close()
                break
            except OSError:
                if server.poll() is not None:
                    raise AssertionError(server.stderr.read().decode())
                time.sleep(0.1)
        else:
            raise AssertionError("Local server did not start")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto("http://127.0.0.1:8013/")
            expect(page.locator("#players .player")).to_have_count(7)
            page.screenshot(path=str(tmp_path / "setup.png"), full_page=True)
            page.locator("#config-name").fill("Browser smoke game")
            page.locator("#config-name").press("Tab")
            page.locator("#players .player").first.get_by_role("button", name="Edit", exact=True).click()
            page.get_by_label("Persona name", exact=True).fill("Smoke test persona")
            page.get_by_label("Persona name", exact=True).press("Tab")
            page.get_by_role("button", name="Markdown", exact=True).click()
            assert "# Smoke test persona" in page.locator("#persona-markdown").input_value()
            page.get_by_role("button", name="Preview", exact=True).click()
            expect(page.locator("#persona-preview")).to_contain_text("Smoke test persona")
            page.get_by_role("button", name="Save persona", exact=True).click()
            expect(page.locator("#persona-dialog")).not_to_be_visible()
            page.locator("#save-config").click()
            expect(page.locator("#notice")).to_contain_text("Configuration saved")
            page.locator("#launch").click()
            expect(page.locator("#viewer")).to_be_visible()
            expect(page.locator("#run-status")).to_contain_text("COMPLETED", timeout=60000)
            expect(page.locator("#seating .seat")).to_have_count(7)
            assert page.locator("#seating .role").count() == 0
            page.locator("#perspective").select_option("omniscient")
            expect(page.locator("#seating .role")).to_have_count(7)
            page.locator("#rewind").click()
            expect(page.locator("#position")).to_contain_text("0 /")
            expect(page.locator("#result-banner")).not_to_be_visible()
            page.locator("#step").click()
            expect(page.locator("#position")).to_contain_text("1 /")
            page.locator("#live").click()
            page.locator("#event-filter").select_option("vote")
            expect(page.locator("#timeline")).to_contain_text("votes")
            page.get_by_role("button", name="Run archive", exact=True).click()
            expect(page.locator("#run-list")).to_contain_text("Browser smoke game")
            page.get_by_role("button", name="Open replay", exact=True).click()
            expect(page.locator("#run-title")).to_have_text("Browser smoke game")
            page.screenshot(path=str(tmp_path / "frontend.png"), full_page=True)
            page.set_viewport_size({"width": 1280, "height": 800})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("button", name="Game setup", exact=True).click()
            page.locator("#player-count").fill("15")
            page.locator("#player-count").press("Tab")
            expect(page.locator("#players .player")).to_have_count(15)
            page.locator("#max-turns").fill("1")
            page.locator("#max-turns").press("Tab")
            page.locator("#launch").click()
            expect(page.locator("#run-status")).to_contain_text("INTERRUPTED", timeout=10000)
            expect(page.locator("#seating .seat")).to_have_count(15)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.screenshot(path=str(tmp_path / "fifteen-players.png"), full_page=True)
            assert not errors
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
