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
from storage import app_db


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
    for index, day in enumerate(["2026-09-21", "2026-10-21", "2026-10-22"]):
        artwork = app_db.create_artwork(
            tweet_id=f"hig-{index}", url=f"https://example.test/{index}",
            title=f"検証用イラスト {index}", posted_at=f"{day}T12:00:00+09:00",
            image_urls=["/demo-artwork.svg", "/demo-artwork.svg?second"],
            db_path=env["APP_DB_PATH"],
        )
        for stage, elapsed, likes in [("5m", 300, 20), ("24h", 86400, 100 + index * 30)]:
            app_db.add_metric_snapshot(
                artwork, stage=stage, elapsed_seconds=elapsed,
                measured_at=f"{day}T13:00:00+09:00", likes=likes,
                retweets=index * 3, impressions=1000, db_path=env["APP_DB_PATH"],
            )
    for day, count in [("2026-09-30", 1000), ("2026-10-01", 1005), ("2026-10-21", 1010)]:
        app_db.add_account_metric(count, f"{day}T12:00:00+09:00", db_path=env["APP_DB_PATH"])
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



def open_section(page, name):
    if name == "about": name = "details"
    target = page.locator(f'#settings [data-section="{name}"]')
    if target.count(): target.evaluate("el => el.open = true")
    if name in {"axes", "style"}:
        page.locator('#settings [data-section="details"]').evaluate("el => el.open = true")

def assert_workspace_fits(page, touch=False):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Tables and MY VIEWS can scroll internally; panel actions must stay inside
    # their cards even after a long title or a different panel becomes first.
    assert page.locator(".panel").evaluate_all(
        """panels => panels.every(panel => {
          const card = panel.getBoundingClientRect();
          return Array.from(panel.querySelectorAll('.panel-head button, .action-menu > summary, .panel-title')).filter(el => el.getClientRects().length).every(el => {
            const box = el.getBoundingClientRect();
            return box.left >= card.left && box.right <= card.right + 1;
          });
        })"""
    )
    if touch:
        assert page.locator(".panel-head button").evaluate_all(
            "buttons => buttons.filter(el => el.getClientRects().length).every(el => el.getBoundingClientRect().width >= 44 && el.getBoundingClientRect().height >= 44)"
        )


def assert_settings_usable(page):
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    dock = page.locator("#settings").bounding_box()
    assert dock["x"] >= 0 and dock["x"] + dock["width"] <= page.viewport_size["width"] + 1
    if page.viewport_size["width"] < 1024:
        preview = page.locator(".panel.is-selected").bounding_box()
        assert preview["height"] >= 44
        assert preview["y"] + preview["height"] <= dock["y"] + 1
    assert page.locator("#settings").evaluate("el => el.scrollWidth <= el.clientWidth")
    assert page.locator("#settings-body").evaluate(
        "el => el.clientHeight >= 44 && el.scrollWidth <= el.clientWidth"
    )
    head = page.locator("#settings .dialog-head").bounding_box()
    page.locator("#settings-body").evaluate("el => el.scrollTop = el.scrollHeight")
    assert page.locator("#settings .dialog-head").bounding_box() == head


def save_view(page, settings=False):
    page.locator("#save-view").click()
    page.wait_for_function("document.querySelector('#save-status').textContent === '✓ 保存済み'")


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
        page.goto(review_server + "/analytics?demo=1#views")
        expect(page.locator(".chart-svg")).to_have_count(4)
        expect(page.locator("#view-lock-state")).to_be_hidden()
        expect(page.locator(".view-edit-state")).to_be_visible()
        expect(page.locator(".view-edit-hint")).to_be_visible()
        assert_workspace_fits(page, width <= 760)

        ids = page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)")
        page.locator('.panel [data-move="1"]').first.click()
        reordered = [ids[1], ids[0], *ids[2:]]
        expect(page.locator("#save-status")).to_have_text("● 未保存")
        assert page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)") == reordered
        expect(page.locator("#view-list .view-dirty")).to_have_count(1)

        # Together with the initial four charts, these cover all seven panel
        # types and a table in the middle of a customized dashboard.
        for kind in ["テーブル", "散布図", "棒グラフ"]:
            page.locator("#add-panel").click()
            page.locator("[data-panel-type]").filter(has_text=kind).click()
            expect(page.locator("#settings")).to_be_visible()
            if kind != "棒グラフ":
                page.locator("#close-settings").click()
        expect(page.locator(".panel")).to_have_count(7)
        bar_id = page.locator(".panel").last.get_attribute("data-panel")
        title = "キャラクターと投稿の反応を比較する長い名前のパネル" * 3
        open_section(page, "details")
        page.get_by_label("名前", exact=True).fill(title)
        assert_settings_usable(page)

        open_section(page, "axes")
        page.get_by_label("集計", exact=True).select_option("median")
        page.locator("[data-add-y]").select_option("retweets")
        assert_settings_usable(page)

        open_section(page, "filters")
        page.locator("#add-filter-group").click()
        page.locator(".filter-rule").first.evaluate("el => el.open = true")
        page.locator('[data-field="filters.0.rules.0.field"]').select_option("character")
        page.locator('[data-field="filters.0.rules.0.op"]').select_option("contains")
        page.locator('[data-field="filters.0.rules.0.value"]').fill("初音")
        assert_settings_usable(page)

        open_section(page, "style")
        page.get_by_role("button", name="配色の説明", exact=True).click()
        page.get_by_role("button", name="カラー #f2785d", exact=True).click()
        legend = page.get_by_label("凡例", exact=True)
        legend.focus()
        page.keyboard.press("Space")
        expect(legend).not_to_be_checked()
        assert legend.locator("..").locator(".toggle-switch").evaluate(
            "el => getComputedStyle(el).outlineStyle !== 'none'"
        )
        page.keyboard.press("Space")
        expect(legend).to_be_checked()
        assert_settings_usable(page)

        open_section(page, "advanced")
        page.locator("#add-formula").click()
        page.locator('[data-example="rate"]').click()
        expect(page.get_by_label("式", exact=True)).to_have_value("likes / impressions * 100")
        assert_settings_usable(page)
        save_view(page, settings=True)
        page.locator("#close-settings").click()
        expect(page.locator(".panel")).to_have_count(7)
        page.get_by_label("ビュー名", exact=True).fill("私のカスタム分析")
        page.keyboard.press("Control+s")
        expect(page.locator("#save-status")).to_have_text("✓ 保存済み")
        expect(page.locator("#view-list .view-dirty")).to_have_count(0)

        original_view = page.locator('#view-list button[aria-current="page"]').get_attribute("data-view")
        expected_ids = page.locator(".panel").evaluate_all("els => els.map(el => el.dataset.panel)")
        page.locator("#view-menu").evaluate("el => el.open = true")
        page.locator("#duplicate-view").click()
        expect(page.locator("#view-name")).to_have_value("私のカスタム分析 のコピー")
        if width <= 760:
            first_view = page.locator("#view-list button").first.get_attribute("data-view")
            page.locator("#view-select").select_option(first_view)
            page.locator("#view-select").select_option(original_view)
        else:
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
        expect(page.get_by_label("名前", exact=True)).to_have_value(title)
        open_section(page, "axes")
        expect(page.get_by_label("集計", exact=True)).to_have_value("median")
        expect(page.locator('[data-remove-y="retweets"]')).to_be_visible()
        open_section(page, "filters")
        page.locator(".filter-rule").first.evaluate("el => el.open = true")
        expect(page.locator('[data-field="filters.0.rules.0.value"]')).to_have_value("初音")
        open_section(page, "style")
        expect(page.get_by_label("色", exact=True)).to_have_value("#f2785d")
        open_section(page, "advanced")
        expect(page.get_by_label("式", exact=True)).to_have_value("likes / impressions * 100")
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
        assert page.locator(".panel-controls button:not([data-settings])").evaluate_all("els => els.every(el => el.disabled)")
        assert_workspace_fits(page, width <= 760)
        page.reload()
        expect(page.locator("#view-lock-state")).to_be_visible()
        page.locator("#toggle-lock").click()
        expect(page.locator("#view-lock-state")).to_be_hidden()
        page.once("dialog", lambda dialog: dialog.accept())
        page.locator(f'[data-panel="{bar_id}"] .action-menu').evaluate("el => el.open = true")
        page.locator(f'[data-panel="{bar_id}"] [data-remove]').click()
        expect(page.locator(".panel")).to_have_count(6)
        save_view(page)
        page.reload()
        expect(page.locator(".panel")).to_have_count(6)
        assert_workspace_fits(page, width <= 760)
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize("width,height", [(1540, 930), (1024, 900), (768, 1024), (374, 852), (320, 740)])
def test_apple_dashboard_calendar_and_detail(review_server, review_browser, width, height):
    from playwright.sync_api import expect

    context = review_browser.new_context(viewport={"width": width, "height": height}, has_touch=width <= 760)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(review_server + "/analytics?month=2026-10")
        expect(page.locator(".metric-posts strong")).to_have_text("2")
        expect(page.locator(".metric-likes strong")).to_have_text("290")
        expect(page.locator(".metric-reposts strong")).to_have_text("9")
        expect(page.locator(".metric-followers strong")).to_have_text("+10")
        overview_panels = [
            ("月間サマリー", "#overview-summary"),
            ("いいね推移", "#overview-likes"),
            ("フォロワー推移", "#overview-followers"),
            ("投稿カレンダー", "#overview-calendar"),
            ("投稿一覧", "#overview-posts"),
        ]
        for _, selector in overview_panels:
            expect(page.locator(selector)).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator(".brand-mark img").evaluate("img => img.complete && img.naturalWidth === 34")
        if width <= 760:
            expect(page.locator(".bottom-nav")).to_be_visible()
            expect(page.locator(".metric-posts")).to_be_hidden()
            page.locator(".mobile-menu-button").click()
            expect(page.locator(".sidebar")).to_be_visible()
            page.keyboard.press("Escape")
            expect(page.locator(".sidebar")).to_be_hidden()
        page.locator("#overview-settings").click()
        for label, _ in overview_panels:
            page.get_by_role("switch", name=label, exact=True).uncheck()
        page.locator("#overview-preferences button[type=submit]").click()
        for _, selector in overview_panels:
            expect(page.locator(selector)).to_be_hidden()
        page.reload()
        for _, selector in overview_panels:
            expect(page.locator(selector)).to_be_hidden()
        page.locator("#overview-settings").click()
        for label, _ in overview_panels:
            page.get_by_role("switch", name=label, exact=True).check()
        page.locator("#overview-lock").click()
        expect(page.get_by_role("switch", name="いいね推移", exact=True)).to_be_disabled()
        page.locator("#overview-preferences button[type=submit]").click()
        page.reload()
        for _, selector in overview_panels:
            expect(page.locator(selector)).to_be_visible()
        expect(page.locator("#overview-followers-chart .daily-bars")).to_be_visible()
        expect(page.locator("#overview-calendar-grid .compact-day")).to_have_count(31)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#overview-month").fill("2026-09")
        expect(page.locator(".metric-likes strong")).to_have_text("100")
        page.locator("#overview-month").fill("2026-10")
        expect(page.locator(".metric-likes strong")).to_have_text("290")
        output_dir = os.getenv("ANALYTICS_REDESIGN_ARTIFACTS")
        if output_dir:
            output = Path(output_dir)
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / f"apple-dashboard-{width}.png"), full_page=True)

        # The dedicated follower page still shows only its own chart.
        page.goto(review_server + "/analytics?month=2026-10#followers")
        expect(page.locator("#overview-followers")).to_be_visible()
        for selector in ["#overview-likes", "#overview-calendar", "#overview-posts"]:
            expect(page.locator(selector)).to_be_hidden()

        page.goto(review_server + "/?month=2026-10")
        expect(page.locator("#month-title")).to_have_text("2026年10月")
        expect(page.locator(".calendar-wrap")).to_be_visible()
        expect(page.locator("#calendar .art-card").first).to_be_visible()
        page.locator(".art-card").first.click()
        page.wait_for_selector(".carousel-image")
        expect(page.locator(".carousel-position")).to_have_text("1 / 2")
        page.get_by_role("button", name="次の画像", exact=True).click()
        expect(page.locator(".carousel-position")).to_have_text("2 / 2")
        for metric in ["retweets", "impressions", "likes"]:
            page.locator(f'[data-metric="{metric}"]').click()
            expect(page.locator(f'[data-metric="{metric}"]')).to_have_class("active")
            page.locator('[data-mode="delta"]').click()
            expect(page.locator(".bar-chart")).to_be_visible()
            page.locator('[data-mode="absolute"]').click()
            expect(page.locator(".line-chart")).to_be_visible()
        point = page.locator(".chart-point").first
        point.focus()
        expect(page.locator("#chart .chart-tooltip")).to_be_visible()
        expect(page.locator("#chart .chart-tooltip")).to_contain_text("20")
        page.locator("[data-x-axis-label]").click()
        expect(page.locator(".chart-legend")).to_contain_text("計測時間")
        page.locator("[data-x-axis-label]").click()
        expect(page.locator(".chart-legend")).to_contain_text("経過時間")
        if width <= 760:
            point = page.locator(".chart-point").first
            point.tap(force=True)
            expect(page.locator("#chart .chart-tooltip")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if output_dir:
            page.screenshot(path=str(output / f"apple-detail-{width}.png"), full_page=True)
        assert not errors
    finally:
        context.close()


def test_apple_overview_missing_data_and_failed_month(review_server, review_browser):
    from playwright.sync_api import expect

    page = review_browser.new_page()
    try:
        page.goto(review_server + "/analytics?month=2026-10")
        expect(page.locator(".metric-likes strong")).to_have_text("290")
        page.route("**/api/calendar?year=2026&month=11", lambda route: route.fulfill(status=503, json={"detail": "unavailable"}))
        page.locator("#overview-month").fill("2026-11")
        expect(page.locator("#overview-error")).to_be_visible()
        expect(page.locator(".overview-metric")).to_have_count(0)
        page.unroute("**/api/calendar?year=2026&month=11")
        page.locator("#overview-refresh").click()
        expect(page.locator(".metric-posts strong")).to_have_text("0")
        expect(page.locator("#overview-highlights")).to_contain_text("投稿はありません")
        page.route("**/api/calendar?year=2026&month=10", lambda route: route.fulfill(json={
            "year": 2026, "month": 10,
            "summary": {"followers": None, "followers_delta": None},
            "days": [{"date": "2026-10-21", "followers_delta": None, "artworks": [{
                "id": "missing", "title": "未計測", "posted_at": "2026-10-21T12:00:00+09:00",
                "image_url": None, "likes": None, "retweets": None,
            }]}],
        }))
        page.locator("#overview-month").fill("2026-10")
        expect(page.locator(".metric-likes strong")).to_have_text("—")
        expect(page.locator(".metric-followers strong")).to_have_text("—")
        expect(page.locator("#overview-likes-chart")).to_contain_text("計測データはありません")
    finally:
        page.close()


def test_detail_delta_preserves_missing_measurements(review_server, review_browser):
    from playwright.sync_api import expect

    calendar = httpx.get(review_server + "/api/calendar?year=2026&month=10", trust_env=False).json()
    artwork_id = next(day["artworks"][0]["id"] for day in calendar["days"] if day["artworks"])
    page = review_browser.new_page(viewport={"width": 374, "height": 852})
    try:
        page.route(f"**/api/artworks/{artwork_id}/metrics", lambda route: route.fulfill(json={"points": [
            {"stage": "5m", "measured_at": "2026-10-21T03:05:00Z", "likes": None},
            {"stage": "15m", "measured_at": "2026-10-21T03:15:00Z", "likes": 50},
            {"stage": "30m", "measured_at": "2026-10-21T03:30:00Z", "likes": 80},
        ]}))
        page.goto(review_server + f"/artworks/{artwork_id}")
        page.locator('[data-mode="delta"]').click()
        expect(page.locator(".chart-value")).to_contain_text("30")
        assert page.locator(".bar").evaluate_all("bars => bars.slice(0, 2).every(bar => getComputedStyle(bar).visibility === 'hidden')")
        page.locator(".bar-wrap").nth(1).dispatch_event("pointerenter", {"clientX": 100, "clientY": 100})
        expect(page.locator("#chart .chart-tooltip")).to_contain_text("—")
    finally:
        page.close()
