"""
scraper/browser.py — Playwright ブラウザ管理 & ステルス設定

認証セッションのロード、ステルスモード設定、ランダムウェイト関数など、
ブラウザ操作の基盤を提供します。
"""

import asyncio
import random
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from playwright.async_api import (
    BrowserContext,
    Page,
    Playwright,
    async_playwright,
)

import config


async def _apply_stealth(page: Page) -> None:
    """ボット検知を回避するためのステルス設定を適用する。"""
    # navigator.webdriver フラグを無効化
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
        });
    """)

    # Chrome プラグイン配列を偽装
    await page.add_init_script("""
        Object.defineProperty(navigator, 'plugins', {
            get: () => [1, 2, 3, 4, 5],
        });
    """)

    # 言語設定を偽装
    await page.add_init_script("""
        Object.defineProperty(navigator, 'languages', {
            get: () => ['ja-JP', 'ja', 'en-US', 'en'],
        });
    """)


async def random_wait(
    min_sec: float | None = None,
    max_sec: float | None = None,
) -> None:
    """ランダムな秒数だけ待機する（アンチスクレイピング対策）。

    Args:
        min_sec: 最小待機秒数。省略時は config 設定値。
        max_sec: 最大待機秒数。省略時は config 設定値。
    """
    _min = min_sec if min_sec is not None else config.WAIT_MIN_SEC
    _max = max_sec if max_sec is not None else config.WAIT_MAX_SEC
    wait_time = random.uniform(_min, _max)
    await asyncio.sleep(wait_time)


@asynccontextmanager
async def create_browser_context(
    headless: bool = True,
) -> AsyncGenerator[tuple[BrowserContext, Page], None]:
    """認証済みブラウザコンテキストとページを提供するコンテキストマネージャ。

    auth_state.json をロードしてセッション Cookie を復元し、
    ステルス設定を適用した状態のページを返します。

    Args:
        headless: ヘッドレスモードで起動するか。デフォルト True。

    Yields:
        tuple[BrowserContext, Page]: (コンテキスト, ページ) のタプル。

    Raises:
        FileNotFoundError: auth_state.json が存在しない場合。
    """
    auth_path = Path(config.X_AUTH_STATE_PATH)
    if not auth_path.exists():
        raise FileNotFoundError(
            f"認証セッションファイルが見つかりません: {auth_path}\n"
            "setup_auth.py を実行して認証セッションを保存してください。"
        )

    playwright: Playwright | None = None
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )

        # ランダムなビューポートサイズ
        viewport_width = random.randint(1280, 1920)
        viewport_height = random.randint(800, 1080)

        context = await browser.new_context(
            storage_state=str(auth_path),
            viewport={"width": viewport_width, "height": viewport_height},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )

        page = await context.new_page()
        await _apply_stealth(page)

        yield context, page

    finally:
        if playwright:
            await playwright.stop()
