"""Exercise URL registration UI with mocked API responses and no X access."""

import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("ANALYTICS_BROWSER_TESTS") != "1",
    reason="Set ANALYTICS_BROWSER_TESTS=1 and install a Playwright browser",
)
WEB = Path(__file__).resolve().parents[1] / "web"


@pytest.mark.parametrize("width", [390, 1440])
def test_url_dialog_and_existing_patrol_on_phone_and_desktop(width, tmp_path):
    from playwright.sync_api import sync_playwright, expect

    calls = []
    result = None
    calendar = {
        "year": 2026, "month": 11, "days": [],
        "summary": {"followers": None, "followers_delta": None, "posts": 0, "likes": 0, "retweets": 0},
    }

    def route_request(route):
        nonlocal result
        path = urlsplit(route.request.url).path
        if path == "/api/calendar":
            route.fulfill(json=calendar)
        elif path == "/api/detect/status":
            route.fulfill(json={"running": False, "result": result})
        elif path == "/api/detect/url":
            calls.append(route.request.post_data_json)
            route.fulfill(status=202, json={"status": "started"})
        elif path == "/api/detect/trigger":
            calls.append("profile")
            result = {"status": "completed", "detected": False}
            route.fulfill(json={"status": "started"})
        else:
            file = WEB / ("index.html" if path == "/" else path.lstrip("/"))
            if file.is_file() and file.is_relative_to(WEB):
                route.fulfill(path=file)
            else:
                route.fulfill(status=404)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
        page = browser.new_page(viewport={"width": width, "height": 900}, has_touch=width < 700)
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.route("**/*", route_request)
        page.goto("http://127.0.0.1:9876/")
        expect(page.locator("#month-title")).not_to_have_text("読み込み中")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        page.locator("#add-post-url").click()
        expect(page.locator("#post-url")).to_be_focused()
        page.keyboard.press("Escape")
        expect(page.locator("#post-url-dialog")).not_to_be_visible()
        expect(page.locator("#add-post-url")).to_be_focused()
        page.locator("#add-post-url").click()
        page.locator("#post-url").fill("https://twitter.com/example/status/123/photo/1?s=20")
        result = {"status": "failed", "message": "画像付きの投稿URLを指定してください。"}
        page.locator("#submit-post-url").click()
        expect(page.locator("#submit-post-url")).to_be_disabled()
        expect(page.locator("#patrol-now")).to_be_disabled()
        expect(page.locator("#post-url-feedback")).to_contain_text("画像付き", timeout=7000)
        expect(page.locator("#submit-post-url")).to_be_enabled()

        result = {"status": "registered", "artwork_id": "art_123", "posted_at": "2026-11-01T12:00:00+00:00"}
        page.locator("#submit-post-url").click()
        expect(page.locator("#post-url-feedback")).to_contain_text("作品を追加しました", timeout=7000)
        assert calls[0]["url"].endswith("/photo/1?s=20")
        bounds = page.locator("#post-url-dialog").bounding_box()
        assert bounds["x"] >= 0 and bounds["x"] + bounds["width"] <= width
        assert page.locator("#post-url").evaluate("el => getComputedStyle(el).fontSize") == "16px"
        page.screenshot(path=str(tmp_path / f"url-registration-{width}.png"))
        page.locator("#close-post-url").click()
        expect(page.locator("#detect-feedback")).to_contain_text("作品を追加しました")
        page.locator("#patrol-now").click()
        expect(page.locator("#detect-feedback")).to_contain_text("新しい作品は見つかりませんでした", timeout=7000)
        assert calls[-1] == "profile"
        assert not errors
        browser.close()
