"""Real Chromium smoke: configure, author persona, launch, view and replay."""

import json
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
            page.get_by_role("button", name="Game setup", exact=True).click()
            page.locator("#script").select_option("bad_moon_rising")
            page.locator("#player-count").fill("7")
            page.locator("#player-count").press("Tab")
            page.locator("#launch").click()
            expect(page.locator("#run-status")).to_contain_text("INTERRUPTED", timeout=10000)
            expect(page.locator("#scenario")).to_contain_text("Bad Moon Rising")
            expect(page.locator("#role-guide .guide-role")).to_have_count(25)
            with page.expect_download() as download:
                page.locator("#export-full-run").click()
            archive_path = tmp_path / "exported-bmr.json"
            download.value.save_as(archive_path)
            archive = json.loads(archive_path.read_text())
            assert archive["run"]["config"]["script"] == "bad_moon_rising"
            assert any(e["audience"] == [] for e in archive["run"]["events"])
            assert len(archive["run"]["personas"]) == 7
            page.get_by_role("button", name="Run archive", exact=True).click()
            page.locator("#import-run").set_input_files(archive_path)
            expect(page.locator("#notice")).to_contain_text("Game imported as a new replay")
            expect(page.locator("#scenario")).to_contain_text("Bad Moon Rising")
            assert archive["run"]["id"][:8] not in page.locator("#run-status").inner_text()
            page.locator("#perspective").select_option("omniscient")
            expect(page.locator("#seating .role")).to_have_count(7)
            for width, height, device in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/clocktower-bmr-export-{device}.png", full_page=True)

            assert not errors
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)


@pytest.mark.browser
def test_chat_scenario_roles_privacy_and_responsive_layout(tmp_path):
    """Replay a deterministic fixture through the real API's audience projections."""
    from clocktower.config import demo_config
    from clocktower.runner import Runner
    from clocktower.storage import Store

    config = demo_config()
    config.name = "Conversation fixture"
    config.roles = ["drunk", "chef", "empath", "slayer", "saint", "baron", "imp"]
    config.shuffle_roles = False
    runner = Runner(config, Store(tmp_path))
    runner.engine.day = 1
    runner.engine.phase = "day"
    runner.engine.emit("phase", {"phase": "day", "day": 1})
    runner.engine.emit("message", {"player": "p1", "target": None, "text": "Let us compare our information."})
    runner.engine.emit(
        "message", {"player": "p1", "target": "p2", "text": "Private clue for Player 2."}, ["p1", "p2"]
    )
    runner.engine.interrupt("Fixture ready for replay")
    runner.save()
    server = subprocess.Popen(
        [sys.executable, "-m", "clocktower.cli", "web", "--port", "8013"],
        env={**os.environ, "CLOCKTOWER_DATA": str(tmp_path)},
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
            page.get_by_role("button", name="Run archive", exact=True).click()
            page.get_by_role("button", name="Open replay", exact=True).click()
            expect(page.locator("#scenario")).to_contain_text("Trouble Brewing")
            expect(page.locator("#game-master")).to_contain_text("Game Master / Storyteller")
            expect(page.locator("#role-guide .guide-role")).to_have_count(22)
            expect(page.locator("#role-roster .roster-role").filter(has_text="Hidden role")).to_have_count(7)
            expect(page.locator("#seating .role")).to_have_count(0)
            public = page.locator('.chat-event.message[data-speaker="p1"][data-recipient="everyone"]')
            expect(public).to_contain_text("Player 1 → Everyone")
            expect(public).to_contain_text("Public speech")
            expect(page.locator(".chat-event.whisper")).to_have_count(0)
            for width, height, device in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/clocktower-chat-public-{device}.png", full_page=True)
            page.locator("#perspective").select_option("p1")
            expect(page.locator("#seating .role")).to_have_count(1)
            expect(page.locator("#seating .role")).to_have_text(
                runner.engine.players[0].shown_role.replace("_", " ")
            )
            expect(page.locator("#role-roster .roster-role").filter(has_text="Hidden role")).to_have_count(6)
            whisper = page.locator('.chat-event.whisper[data-speaker="p1"][data-recipient="p2"]')
            expect(whisper).to_contain_text("Player 1 → Player 2")
            expect(whisper).to_contain_text("Private whisper")
            page.locator("#perspective").select_option("p3")
            expect(page.locator(".chat-event.whisper")).to_have_count(0)
            page.get_by_role("button", name="Reveal all roles · Storyteller view", exact=True).click()
            expect(page.locator("#perspective")).to_have_value("omniscient")
            expect(page.locator("#seating .role")).to_have_count(7)
            expect(page.locator("#seating .role").first).to_have_text("drunk")
            expect(page.locator("#role-roster .roster-role").filter(has_text="Hidden role")).to_have_count(0)
            expect(page.locator(".chat-event.whisper")).to_have_count(1)
            for width, height, device in [(1440, 1000, "desktop"), (390, 844, "mobile")]:
                page.set_viewport_size({"width": width, "height": height})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(path=f"/tmp/clocktower-chat-omniscient-{device}.png", full_page=True)
            page.locator("#rewind").click()
            expect(page.locator("#seating .role")).to_have_count(0)
            expect(page.locator("#role-roster .roster-role").filter(has_text="Hidden role")).to_have_count(7)
            expect(page.locator(".chat-event.message")).to_have_count(0)
            page.locator("#step").click()
            expect(page.locator("#seating .role")).to_have_count(0)
            page.locator("#live").click()
            page.locator("#event-filter").select_option(label="Game Master")
            expect(page.locator(".chat-event.player-event")).to_have_count(0)
            assert page.locator(".chat-event.gm-event").count() > 0
            assert not errors
            browser.close()
    finally:
        server.terminate()
        server.wait(timeout=10)
