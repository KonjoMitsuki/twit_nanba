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

    def save_changes(target, in_settings=False):
        target.locator("#save-settings" if in_settings else "#save-view").click()
        target.wait_for_function(
            "document.querySelector('#save-status').textContent === '保存済み'"
        )

    def open_account_menu(target):
        if not target.locator("#profile-user").is_visible():
            target.locator(".mobile-menu-button").click()

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
        artwork_id = app_db.create_artwork(
            tweet_id=suffix,
            url=f"https://example.com/{suffix}",
            title=suffix,
            posted_at="2026-10-10T00:00:00+00:00",
            image_urls=image_urls,
            db_path=env["APP_DB_PATH"],
            characters=["A", "B"]
            if suffix == "photo"
            else ["A"]
            if suffix == "broken"
            else [],
        )
        app_db.add_metric_snapshot(
            artwork_id,
            stage="24h",
            elapsed_seconds=86400,
            measured_at="2026-10-11T00:00:00+00:00",
            likes={"photo": 10, "broken": 20, "empty": 30}[suffix],
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
            # Plain http://IP is not a secure context, so crypto.randomUUID is
            # missing there. The page must still boot and render its templates.
            insecure = browser.new_page()
            insecure_errors = []
            insecure.on(
                "pageerror", lambda error: insecure_errors.append(str(error))
            )
            insecure.add_init_script(
                "Object.defineProperty(Crypto.prototype, 'randomUUID', "
                "{ value: undefined, configurable: true });"
            )
            insecure.goto(url + "/analytics?demo=1#views")
            insecure.wait_for_selector(".chart-svg")
            assert not insecure_errors
            insecure.close()
            character_page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            character_errors = []
            character_page.on(
                "pageerror", lambda error: character_errors.append(str(error))
            )
            character_page.goto(url + "/analytics?demo=1#views")
            character_page.wait_for_selector(".chart-svg")
            character_page.locator(
                "#view-list button", has_text="作品テーブル"
            ).click()
            character_page.wait_for_selector(".character-cell")
            character_page.locator(".character-cell").first.click()
            character_page.wait_for_selector("#character-dialog[open]")
            suggestions = character_page.locator("#character-suggestions li")
            assert 0 < suggestions.count() <= 5
            suggestion_name = suggestions.first.locator("span").inner_text()
            character_page.fill("#character-name", suggestion_name)
            character_page.wait_for_function(
                "document.querySelectorAll('#character-suggestions li').length === 1"
            )
            character_page.press("#character-name", "Tab")
            assert (
                character_page.locator(
                    ".character-chip-selected", has_text=suggestion_name
                ).count()
                == 1
            )
            character_page.fill("#character-name", "検証キャラ")
            character_page.locator("#add-character-form button").click()
            assert (
                character_page.locator(
                    ".character-chip-selected", has_text="検証キャラ"
                ).count()
                == 1
            )
            character_page.keyboard.press("Escape")
            assert not character_page.locator("#character-suggestions").is_visible()
            character_page.keyboard.press("Escape")
            character_page.wait_for_function(
                "!document.querySelector('#character-dialog').open"
            )
            assert not character_errors
            character_page.close()
            page = browser.new_page(
                viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
            )
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(url + "/analytics?demo=1#views")
            page.wait_for_function(
                "document.querySelectorAll('.chart-svg').length === 4"
            )
            assert page.locator("#save-status").inner_text() == "保存済み"
            assert page.locator("#save-view").is_disabled()
            assert page.locator("#single-tabs").is_hidden()
            assert page.locator(".panel-error").count() == 0
            page.get_by_role(
                "button", name="表・グラフを追加", exact=True
            ).click()
            assert page.locator("#panel-type-dialog").is_visible()
            assert page.locator("[data-panel-type]").count() == 7
            page.keyboard.press("Escape")
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            assert page.locator("#settings-summary").is_visible()
            assert page.locator("[data-source-card]").count() == 3
            assert page.locator(".chart-card").count() == 7
            assert page.locator("#undo-settings").is_disabled()
            page.locator(".source-card").filter(has_text="作品を比較").click()
            assert "作品を比較" in page.locator("#settings-summary").inner_text()
            assert page.get_by_label("投稿からどの時点？", exact=True).is_visible()
            page.locator("#undo-settings").click()
            assert "投稿後の伸びを追う" in page.locator("#settings-summary").inner_text()
            assert page.get_by_label("投稿からどの時点？", exact=True).count() == 0
            page.get_by_role("button", name="表示", exact=True).click()
            page.get_by_label("横軸・分類", exact=True).select_option("measured_at")
            assert page.locator("#undo-settings").is_enabled()
            page.locator("#undo-settings").click()
            assert (
                page.get_by_label("横軸・分類", exact=True).input_value()
                == "elapsed_hours"
            )
            page.get_by_label("横軸・分類", exact=True).select_option("measured_at")
            assert page.locator("#save-status").inner_text() == "未保存"
            assert page.locator("#save-view").is_enabled()
            assert page.locator("#view-list .view-dirty").count() == 1
            page.wait_for_timeout(900)
            assert page.locator("#save-status").inner_text() == "未保存"
            save_changes(page, in_settings=True)
            assert page.locator("#view-list .view-dirty").count() == 0
            assert page.locator("#save-view").is_disabled()
            page.keyboard.press("Escape")
            page.reload()
            page.wait_for_selector(".chart-svg")
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="表示", exact=True).click()
            assert (
                page.get_by_label("横軸・分類", exact=True).input_value()
                == "measured_at"
            )
            page.keyboard.press("Escape")
            page.locator("#toggle-lock").click()
            page.wait_for_selector("#view-lock-state:not([hidden])")
            assert page.locator("#toggle-lock").get_attribute("aria-pressed") == "true"
            assert not page.get_by_label("ビュー名", exact=True).is_editable()
            assert page.locator("#layout").is_disabled()
            assert page.get_by_role(
                "button", name="表・グラフを追加", exact=True
            ).is_disabled()
            assert page.get_by_role(
                "button", name="ビューを削除", exact=True
            ).is_disabled()
            assert page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).is_disabled()
            assert page.locator("#view-list .view-lock-mark").count() == 1
            page.reload()
            page.wait_for_selector("#view-lock-state:not([hidden])")
            assert not page.get_by_label("ビュー名", exact=True).is_editable()
            page.locator("#toggle-lock").click()
            page.wait_for_function(
                "document.querySelector('#view-lock-state').hidden"
            )
            assert page.get_by_label("ビュー名", exact=True).is_editable()
            assert page.get_by_role(
                "button", name="表・グラフを追加", exact=True
            ).is_enabled()
            page.locator("#demo-user").select_option("demo_b")
            page.wait_for_selector(".chart-svg")
            page.get_by_role(
                "button", name="投稿後のいいね推移の設定", exact=True
            ).click()
            page.get_by_role("button", name="表示", exact=True).click()
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
            page.get_by_role("button", name="詳細", exact=True).click()
            page.locator('[data-example="rate"]').click()
            assert (
                page.get_by_label("計算式", exact=True).input_value()
                == "likes / impressions * 100"
            )
            page.goto(url + "/analytics#views")
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
            page.get_by_role("button", name="表示", exact=True).click()
            assert page.get_by_text("表示列の選択", exact=True).is_visible()
            assert page.get_by_text("行のグループ化", exact=True).is_visible()
            page.get_by_label("投稿写真を表示", exact=True).locator("..").click()
            assert not page.get_by_label("投稿写真を表示", exact=True).is_checked()
            save_changes(page, in_settings=True)
            page.keyboard.press("Escape")
            page.reload()
            page.wait_for_selector(".table-scroll")
            assert page.locator(".artwork-thumbnail").count() == 0
            page.get_by_label("ビュー名", exact=True).fill("利用者Aの分析")
            save_changes(page)
            open_account_menu(page)
            page.locator("#profile-user").select_option("profile_b")
            page.wait_for_selector("#empty-views:not([hidden])")
            assert page.locator("#view-list button").count() == 0
            open_account_menu(page)
            page.locator("#profile-user").select_option("profile_a")
            page.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            page.once("dialog", lambda dialog: dialog.accept("ミツキ"))
            open_account_menu(page)
            page.get_by_role("button", name="名前を変更", exact=True).click()
            page.wait_for_function(
                "document.querySelector('#profile-user').selectedOptions[0].textContent === 'ミツキ'"
            )
            page.once("dialog", lambda dialog: dialog.accept("分析担当"))
            open_account_menu(page)
            page.locator("#profile-user").select_option("__new__")
            page.wait_for_selector("#empty-views:not([hidden])")
            assert page.locator("#profile-user option").count() == 4
            open_account_menu(page)
            page.locator("#profile-user").select_option("profile_a")
            page.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            another = browser.new_page()
            another.goto(url + "/analytics#views")
            another.wait_for_function(
                "document.querySelector('#view-name').value === '利用者Aの分析'"
            )
            assert another.locator("#profile-user").input_value() == "profile_a"
            another.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            another.get_by_role("button", name="表示", exact=True).click()
            another.get_by_label("グループ化する項目", exact=True).select_option(
                "character"
            )
            another.get_by_label("並べ替え項目 1", exact=True).select_option("likes")
            another.get_by_role("button", name="並べ替え条件を追加", exact=True).click()
            another.get_by_label("並べ替え項目 2", exact=True).select_option("date")
            save_changes(another, in_settings=True)
            another.keyboard.press("Escape")
            another.wait_for_function(
                "document.querySelectorAll('.table-group').length === 3"
            )
            first = another.locator(".table-group").first
            assert first.locator("summary span").first.inner_text() == "A"
            assert first.locator(".table-group-count").inner_text() == "2行"
            assert (
                first.locator("tbody tr").first.locator("td").first.inner_text()
                == "broken"
            )
            first.locator("summary").click()
            with another.expect_response(
                lambda response: (
                    "/api/analytics/views/" in response.url
                    and response.request.method == "PATCH"
                    and response.status == 200
                )
            ):
                save_changes(another)
            another.reload()
            another.wait_for_selector(".table-group")
            assert another.locator(".table-group").first.evaluate("el => !el.open")
            another.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            another.get_by_role("button", name="表示", exact=True).click()
            assert (
                another.get_by_label("並べ替え項目 1", exact=True).input_value()
                == "likes"
            )
            assert (
                another.get_by_label("並べ替え項目 2", exact=True).input_value()
                == "date"
            )
            another.get_by_label("複数の値がある行", exact=True).select_option(
                "combination"
            )
            save_changes(another, in_settings=True)
            another.keyboard.press("Escape")
            another.wait_for_function(
                "Array.from(document.querySelectorAll('.table-group > summary')).some(el => el.textContent.includes('A + B'))"
            )
            another.set_viewport_size({"width": 375, "height": 812})
            assert another.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            )
            # Return many rows through the real query interface to verify pagination.
            grouped_rows = [
                {
                    "row_id": str(i),
                    "artwork_id": str(i),
                    "title": f"Row {i}",
                    "characters": ["A"],
                    "character": "A",
                    "likes": i,
                    "date": "2026-10-10",
                    "image_urls": [],
                }
                for i in range(123)
            ]

            def paged_result(route):
                route.fulfill(
                    json={
                        "rows": grouped_rows,
                        "points": [],
                        "fields": {
                            "title": "作品名",
                            "character": "キャラクター",
                            "date": "日付",
                            "likes": "いいね",
                        },
                        "artwork_count": len(grouped_rows),
                        "missing_stage_count": 0,
                        "excluded_count": 0,
                        "warnings": [],
                    }
                )

            another.route("**/api/analytics/query", paged_result)
            another.get_by_role("button", name="更新", exact=True).click()
            another.wait_for_function(
                "document.querySelector('.table-group-count')?.textContent === '123行'"
            )
            assert another.locator(".table-group tbody tr").count() == 50
            another.locator('.table-group [data-group-page="1"]').click()
            assert another.locator(".table-group tbody tr").count() == 50
            another.locator('.table-group [data-group-page="1"]').click()
            assert another.locator(".table-group tbody tr").count() == 23
            grouped_rows[:] = [
                row | {"characters": [f"A{i}"], "character": f"A{i}"}
                for i, row in enumerate(grouped_rows[:12])
            ]
            another.get_by_role("button", name="更新", exact=True).click()
            another.wait_for_function(
                "document.querySelectorAll('.table-group').length === 10"
            )
            another.locator('[data-page="1"]').click()
            assert another.locator(".table-group").count() == 2
            another.unroute("**/api/analytics/query", paged_result)
            another.set_viewport_size({"width": 1440, "height": 1000})
            another.on("pageerror", lambda error: errors.append(str(error)))
            another.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            another.locator('.chart-card').filter(has_text="散布図").click()
            another.get_by_role("button", name="表示", exact=True).click()
            another.get_by_label("横軸・分類", exact=True).select_option("likes")
            another.get_by_label("系列・色分け", exact=True).select_option("character")
            assert another.get_by_label("集計方法", exact=True).count() == 0
            another.wait_for_function(
                "document.querySelectorAll('.scatter-point').length === 4"
            )
            save_changes(another, in_settings=True)
            another.keyboard.press("Escape")
            another.reload()
            another.wait_for_function(
                "document.querySelectorAll('.scatter-point').length === 4"
            )
            assert another.locator(".chart-svg path[stroke-width='2.2']").count() == 0
            another.locator('[data-tip^="broken"]').click()
            assert another.locator(".chart-artwork-title").inner_text() == "broken"
            assert (
                another.locator('.chart-artwork-metric[aria-label="いいね 20"]').count()
                == 1
            )
            another.wait_for_function(
                "document.querySelector('.chart-artwork-placeholder')?.hidden === false"
            )
            assert (
                another.locator(".chart-artwork-placeholder").inner_text()
                == "読み込めません"
            )
            another.locator('[data-tip^="photo"]').last.click()
            another.wait_for_function(
                "document.querySelector('.chart-artwork-photo img')?.naturalWidth > 0"
            )
            assert another.locator(".chart-artwork-title").inner_text() == "photo"
            assert another.locator(".chart-artwork-image-count").inner_text() == "2枚"
            another.locator('[data-tip^="broken"]').click()
            assert (
                "broken" in another.locator(".chart-tooltip").inner_text()
                or "photo" in another.locator(".chart-tooltip").inner_text()
            )
            another.locator("[data-legend='B|likes']").click()
            assert another.locator(".scatter-point").count() == 3
            another.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            another.get_by_role("button", name="表示", exact=True).click()
            assert (
                another.get_by_label("横軸・分類", exact=True).input_value() == "likes"
            )
            another.get_by_role("button", name="見た目", exact=True).click()
            another.get_by_label("横軸の最小値", exact=True).fill("0")
            another.get_by_label("縦軸の最大値", exact=True).fill("40")
            another.get_by_label("横軸の目盛り間隔", exact=True).select_option("manual")
            another.get_by_label("横軸の目盛り間隔の値", exact=True).fill("5")
            another.get_by_label("縦軸の目盛り間隔", exact=True).select_option("manual")
            another.get_by_label("縦軸の目盛り間隔の値", exact=True).fill("10")
            save_changes(another, in_settings=True)
            another.set_viewport_size({"width": 375, "height": 812})
            another.keyboard.press("Escape")
            another.reload()
            another.wait_for_selector(".scatter-point")
            another.get_by_role("button", name="作品テーブルの設定", exact=True).click()
            another.get_by_role("button", name="見た目", exact=True).click()
            assert another.get_by_label("横軸の最小値", exact=True).input_value() == "0"
            assert (
                another.get_by_label("縦軸の最大値", exact=True).input_value() == "40"
            )
            assert (
                another.get_by_label("横軸の目盛り間隔", exact=True).input_value()
                == "manual"
            )
            assert (
                another.get_by_label("横軸の目盛り間隔の値", exact=True).input_value()
                == "5"
            )
            assert (
                another.get_by_label("縦軸の目盛り間隔の値", exact=True).input_value()
                == "10"
            )
            another.get_by_label("横軸の目盛り間隔", exact=True).select_option("auto")
            assert another.get_by_label("横軸の目盛り間隔の値", exact=True).count() == 0
            another.keyboard.press("Escape")
            another.wait_for_selector(".scatter-point")
            another.locator('[data-tip^="broken"]').click()
            assert another.evaluate(
                "document.documentElement.scrollWidth <= innerWidth"
            )
            another.get_by_role(
                "button", name="表・グラフを追加", exact=True
            ).click()
            assert another.locator("[data-panel-type]").count() == 7
            another.locator("[data-panel-type]").filter(has_text="円").click()
            assert another.locator("#settings").evaluate("el => el.open")
            assert "円" in another.locator("#settings-type-badge").inner_text()
            another.keyboard.press("Escape")
            remove_pie = another.get_by_role(
                "button", name="キャラクター別の反応構成を削除", exact=True
            ).last
            remove_pie.wait_for()
            another.once("dialog", lambda dialog: dialog.accept())
            remove_pie.click()
            save_changes(another)
            with another.expect_response(
                lambda response: (
                    response.url.endswith("/lock")
                    and response.request.method == "PATCH"
                    and response.status == 200
                )
            ):
                another.locator("#toggle-lock").click()
            another.wait_for_selector("#view-lock-state:not([hidden])")
            assert another.get_by_role(
                "button", name="ビューを削除", exact=True
            ).is_disabled()
            another.reload()
            another.wait_for_selector("#view-lock-state:not([hidden])")
            assert not another.get_by_label("ビュー名", exact=True).is_editable()
            with another.expect_response(
                lambda response: (
                    response.url.endswith("/lock")
                    and response.request.method == "PATCH"
                    and response.status == 200
                )
            ):
                another.locator("#toggle-lock").click()
            another.wait_for_function(
                "document.querySelector('#view-lock-state').hidden"
            )
            assert another.get_by_label("ビュー名", exact=True).is_editable()
            assert not errors
            browser.close()
    finally:
        process.terminate()
        process.wait(timeout=10)
