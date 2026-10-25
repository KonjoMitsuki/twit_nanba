"""Opt-in layout regression checks using only demo data and a temporary DB."""

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


@pytest.fixture(scope="module")
def review_server(tmp_path_factory):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(tmp_path_factory.mktemp("analytics-layout") / "test.db")
    for key in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_ALLOWED_EMAILS"]:
        env[key] = ""
    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        url = f"http://127.0.0.1:{port}"
        for _ in range(100):
            try:
                if httpx.get(url + "/api/health", timeout=0.5, trust_env=False).status_code == 200:
                    break
            except httpx.TransportError:
                time.sleep(0.05)
        else:
            pytest.fail("The isolated layout-test server did not start")
        yield url
    finally:
        process.terminate()
        process.wait(timeout=10)


@pytest.fixture(scope="module")
def review_browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            executable_path=os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or shutil.which("chromium"),
            headless=True,
            args=["--no-sandbox"],
        )
        yield browser
        browser.close()


def assert_workspace_fits(page, touch=False):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Tables and MY VIEWS can scroll internally; panel actions must stay inside
    # their cards even after a long title or a different panel becomes first.
    assert page.locator(".panel").evaluate_all(
        """panels => panels.every(panel => {
          const card = panel.getBoundingClientRect();
          return Array.from(panel.querySelectorAll('.panel-head button, .panel-title')).every(el => {
            const box = el.getBoundingClientRect();
            return box.left >= card.left && box.right <= card.right + 1;
          });
        })"""
    )
    if touch:
        assert page.locator(".panel-head button").evaluate_all(
            "buttons => buttons.every(el => el.getBoundingClientRect().width >= 44 && el.getBoundingClientRect().height >= 44)"
        )


def assert_settings_usable(page):
    assert page.locator("#settings").evaluate("el => el.scrollWidth <= el.clientWidth")
    assert page.locator("#settings-body").evaluate(
        "el => el.clientHeight >= 44 && el.scrollWidth <= el.clientWidth"
    )
    assert page.locator(".settings-tabs button, .settings-footer button").evaluate_all(
        """buttons => buttons.every(el => {
          const box = el.getBoundingClientRect();
          return box.left >= 0 && box.right <= innerWidth + 1 && box.top >= 0 && box.bottom <= innerHeight + 1;
        })"""
    )
    footer = page.locator(".settings-footer").bounding_box()
    page.locator("#settings-body").evaluate("el => el.scrollTop = el.scrollHeight")
    assert page.locator(".settings-footer").bounding_box() == footer


def save_view(page, settings=False):
    page.locator("#save-settings" if settings else "#save-view").click()
    page.wait_for_function("document.querySelector('#save-status').textContent === '保存済み'")


@pytest.mark.parametrize("width,height", [(1440, 1000), (1024, 900), (768, 1024), (390, 844), (320, 740), (812, 375)])
def test_customized_layout_save_switch_lock_and_settings(review_server, review_browser, width, height):
    from playwright.sync_api import expect

    context = review_browser.new_context(
        viewport={"width": width, "height": height},
        reduced_motion="reduce",
        has_touch=width <= 760,
        is_mobile=width <= 760,
    )
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(review_server + "/analytics?demo=1")
        expect(page.locator(".chart-svg")).to_have_count(4)
        expect(page.locator("#view-lock-state")).to_be_hidden()
        expect(page.locator(".view-edit-state")).to_be_visible()
        expect(page.locator(".view-edit-hint")).to_be_visible()
        assert_workspace_fits(page, width <= 760)

        ids = page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)")
        page.locator('.panel [data-move="1"]').first.click()
        reordered = [ids[1], ids[0], *ids[2:]]
        expect(page.locator("#save-status")).to_have_text("未保存")
        assert page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)") == reordered
        expect(page.locator("#view-list .view-dirty")).to_have_count(1)

        # Together with the initial four charts, these cover all seven panel
        # types and a table in the middle of a customized dashboard.
        for kind in ["テーブル", "散布図", "棒グラフ"]:
            page.locator("#add-panel").click()
            page.locator("[data-panel-type]").filter(has_text=kind).click()
            expect(page.locator("#settings")).to_be_visible()
            if kind != "棒グラフ":
                page.locator("#done-settings").click()
        expect(page.locator(".panel")).to_have_count(7)
        bar_id = page.locator(".panel").last.get_attribute("data-panel")
        title = "キャラクターと投稿の反応を比較する長い名前のパネル" * 3
        page.get_by_label("パネル名", exact=True).fill(title)
        assert_settings_usable(page)

        page.get_by_role("button", name="表示", exact=True).click()
        page.get_by_label("集計方法", exact=True).select_option("median")
        page.locator('[data-y="retweets"]').check()
        assert_settings_usable(page)

        page.get_by_role("button", name="絞り込み", exact=True).click()
        page.locator("#add-filter-group").click()
        page.locator('[data-field="filters.0.rules.0.field"]').select_option("character")
        page.locator('[data-field="filters.0.rules.0.op"]').select_option("contains")
        page.locator('[data-field="filters.0.rules.0.value"]').fill("初音")
        assert_settings_usable(page)

        page.get_by_role("button", name="見た目", exact=True).click()
        page.get_by_role("button", name="カラー #f2785d", exact=True).click()
        legend = page.get_by_label("凡例を表示", exact=True)
        legend.focus()
        page.keyboard.press("Space")
        expect(legend).not_to_be_checked()
        assert legend.locator("..").locator(".toggle-switch").evaluate(
            "el => getComputedStyle(el).outlineStyle !== 'none'"
        )
        page.keyboard.press("Space")
        expect(legend).to_be_checked()
        assert_settings_usable(page)

        page.get_by_role("button", name="詳細", exact=True).click()
        page.locator('[data-example="rate"]').click()
        expect(page.get_by_label("計算式", exact=True)).to_have_value("likes / impressions * 100")
        assert_settings_usable(page)
        save_view(page, settings=True)
        page.locator("#done-settings").click()
        expect(page.locator(".panel")).to_have_count(7)
        page.get_by_label("ビュー名", exact=True).fill("私のカスタム分析")
        page.keyboard.press("Control+s")
        expect(page.locator("#save-status")).to_have_text("保存済み")
        expect(page.locator("#view-list .view-dirty")).to_have_count(0)

        original_view = page.locator('#view-list button[aria-current="page"]').get_attribute("data-view")
        expected_ids = page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)")
        page.locator("#duplicate-view").click()
        expect(page.locator("#view-name")).to_have_value("私のカスタム分析 のコピー")
        page.locator("#view-list button").first.click()
        page.locator(f'#view-list [data-view="{original_view}"]').click()
        expect(page.locator("#view-name")).to_have_value("私のカスタム分析")
        expect(page.locator(".panel")).to_have_count(7)
        assert page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)") == expected_ids
        assert_workspace_fits(page, width <= 760)

        artifacts = os.getenv("ANALYTICS_REDESIGN_ARTIFACTS")
        if artifacts:
            output = Path(artifacts)
            output.mkdir(parents=True, exist_ok=True)
            page.evaluate("window.scrollTo(0, 0)")
            page.screenshot(path=str(output / f"customized-{width}x{height}.png"), full_page=True)
            page.screenshot(path=str(output / f"customized-viewport-{width}x{height}.png"))

        page.locator("#layout").select_option("single")
        expect(page.locator("#single-tabs button")).to_have_count(7)
        page.locator("#single-tabs button").first.click()
        expect(page.locator(".panel")).to_have_count(1)
        save_view(page)
        page.reload()
        expect(page.locator("#layout")).to_have_value("single")
        expect(page.locator(".panel")).to_have_count(1)
        assert page.locator(".panel").get_attribute("data-panel") == expected_ids[0]
        page.locator("#layout").select_option("dashboard")
        expect(page.locator(".panel")).to_have_count(7)
        save_view(page)
        page.reload()
        expect(page.locator(".panel")).to_have_count(7)
        assert page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)") == expected_ids

        page.locator(f'[data-panel="{bar_id}"] [data-settings]').click()
        expect(page.get_by_label("パネル名", exact=True)).to_have_value(title)
        page.get_by_role("button", name="表示", exact=True).click()
        expect(page.get_by_label("集計方法", exact=True)).to_have_value("median")
        expect(page.locator('[data-y="retweets"]')).to_be_checked()
        page.get_by_role("button", name="絞り込み", exact=True).click()
        expect(page.locator('[data-field="filters.0.rules.0.value"]')).to_have_value("初音")
        page.get_by_role("button", name="見た目", exact=True).click()
        expect(page.get_by_label("メインカラー", exact=True)).to_have_value("#f2785d")
        page.get_by_role("button", name="詳細", exact=True).click()
        expect(page.get_by_label("計算式", exact=True)).to_have_value("likes / impressions * 100")
        assert_settings_usable(page)
        if artifacts:
            page.screenshot(path=str(output / f"customized-settings-{width}x{height}.png"))
        page.keyboard.press("Escape")

        page.locator("#toggle-lock").click()
        expect(page.locator("#view-lock-state")).to_be_visible()
        expect(page.locator(".view-edit-state")).to_be_hidden()
        expect(page.locator(".view-edit-hint")).to_be_hidden()
        expect(page.locator("#add-panel")).to_be_disabled()
        expect(page.locator("#view-name")).not_to_be_editable()
        assert page.locator(".panel-controls button").evaluate_all("els => els.every(el => el.disabled)")
        assert_workspace_fits(page, width <= 760)
        page.reload()
        expect(page.locator("#view-lock-state")).to_be_visible()
        page.locator("#toggle-lock").click()
        expect(page.locator("#view-lock-state")).to_be_hidden()
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(f'[data-panel="{bar_id}"] [data-remove]').click()
        expect(page.locator(".panel")).to_have_count(6)
        save_view(page)
        page.reload()
        expect(page.locator(".panel")).to_have_count(6)
        assert_workspace_fits(page, width <= 760)
        assert not errors
    finally:
        context.close()
