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

from storage import app_db

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
    for suffix, image_urls in [
        (
            "photo",
            [
                f"http://127.0.0.1:{port}/demo-artwork.svg",
                f"http://127.0.0.1:{port}/demo-artwork.svg?second",
            ],
        ),
        ("broken", [f"http://127.0.0.1:{port}/missing-photo.svg"]),
        ("empty", []),
    ]:
        app_db.create_artwork(
            tweet_id=suffix,
            url=f"https://example.com/{suffix}",
            title=suffix,
            posted_at="2026-10-10T00:00:00+00:00",
            image_urls=image_urls,
            db_path=env["APP_DB_PATH"],
        )
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
            page.goto(url + "/analytics")
            page.wait_for_selector("#empty-views:not([hidden])")
            assert page.locator("#profile-user").input_value() == "profile_a"
            page.locator('#starter-templates [data-template="0"]').click()
            page.wait_for_selector("#view-name")
            page.wait_for_function(
                "Array.from(document.querySelectorAll('.artwork-thumbnail img')).some(img => img.naturalWidth > 0)"
            )
            assert page.locator(".artwork-image-count").inner_text() == "2枚"
            page.wait_for_function(
                "Array.from(document.querySelectorAll('.artwork-image-empty')).some(el => !el.hidden && el.textContent === '読み込めません')"
            )
            assert (
                page.locator(".artwork-image-empty", has_text="写真なし").count() == 1
            )
            assert "/artworks/" in page.locator(
                "a.artwork-thumbnail"
            ).first.get_attribute("href")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            page.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            page.get_by_role("button", name="軸・集計", exact=True).click()
            page.get_by_label("投稿写真を表示", exact=True).uncheck()
            page.wait_for_function(
                "document.querySelector('#save-status').textContent === 'すべて保存済み'"
            )
            page.keyboard.press("Escape")
            page.reload()
            page.wait_for_selector(".table-scroll")
            assert page.locator(".artwork-thumbnail").count() == 0
            page.get_by_label("ビュー名", exact=True).fill("利用者Aの分析")
            page.wait_for_function(
                "document.querySelector('#save-status').textContent === 'すべて保存済み'"
            )
            page.locator("#profile-user").select_option("profile_b")
            page.wait_for_selector("#empty-views:not([hidden])")
            assert page.locator("#view-list button").count() == 0
            page.locator("#profile-user").select_option("profile_a")
            page.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            page.once("dialog", lambda dialog: dialog.accept("ミツキ"))
            page.get_by_role("button", name="名前を変更", exact=True).click()
            page.wait_for_function(
                "document.querySelector('#profile-user').selectedOptions[0].textContent === 'ミツキ'"
            )
            page.once("dialog", lambda dialog: dialog.accept("分析担当"))
            page.locator("#profile-user").select_option("__new__")
            page.wait_for_selector("#empty-views:not([hidden])")
            assert page.locator("#profile-user option").count() == 4
            page.locator("#profile-user").select_option("profile_a")
            page.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            another = browser.new_page()
            another.goto(url + "/analytics")
            another.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            assert another.locator("#profile-user").input_value() == "profile_a"
            assert not errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
