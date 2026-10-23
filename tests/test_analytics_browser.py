"""Opt-in end-to-end smoke test; uses synthetic data and an isolated empty DB."""

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ANALYTICS_BROWSER_TESTS") != "1",
    reason="Set ANALYTICS_BROWSER_TESTS=1 and install a Playwright browser",
)


def test_personal_designer_on_desktop_and_phone(tmp_path):
    from playwright.sync_api import sync_playwright

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(tmp_path / "browser.db")
    for key in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_ALLOWED_EMAILS"]:
        env[key] = ""
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if (
                    httpx.get(
                        url + "/api/health", timeout=0.5, trust_env=False
                    ).status_code
                    == 200
                ):
                    break
            except httpx.TransportError:
                time.sleep(0.05)
        else:
            pytest.fail("The isolated browser-test server did not start")
        with sync_playwright() as playwright:
            executable = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or shutil.which(
                "chromium"
            )
            browser = playwright.chromium.launch(
                executable_path=executable, headless=True, args=["--no-sandbox"]
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + "/analytics?demo=1")
            page.wait_for_function(
                "document.querySelectorAll('.chart-svg').length === 4"
            )
            assert page.locator("#single-tabs").is_hidden()
            assert page.locator(".panel-error").count() == 0
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="軸・集計", exact=True).click()
            page.get_by_label("横軸・分類", exact=True).select_option("measured_at")
            page.wait_for_function(
                "document.querySelector('#save-status').textContent === 'すべて保存済み'"
            )
            page.keyboard.press("Escape")
            page.reload()
            page.wait_for_selector(".chart-svg")
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="軸・集計", exact=True).click()
            assert (
                page.get_by_label("横軸・分類", exact=True).input_value()
                == "measured_at"
            )
            page.keyboard.press("Escape")
            page.locator("#demo-user").select_option("demo_b")
            page.wait_for_selector(".chart-svg")
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="軸・集計", exact=True).click()
            assert (
                page.get_by_label("横軸・分類", exact=True).input_value()
                == "elapsed_hours"
            )
            page.keyboard.press("Escape")
            for width, height in [(375, 812), (812, 375)]:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(200)
                assert page.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                )
            page.set_viewport_size({"width": 375, "height": 812})
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="計算式", exact=True).click()
            page.get_by_role(
                "button", name="反応率：likes / impressions * 100", exact=True
            ).click()
            assert (
                page.get_by_label("計算式", exact=True).input_value()
                == "likes / impressions * 100"
            )
            assert not errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
