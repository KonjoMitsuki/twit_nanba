"""
scraper/fans.py — いいねモーダルからの反応者一覧取得

ツイートのいいね数リンクをクリックしてモーダルを開き、
表示されたユーザーの @screen_name を抽出します。
スクロール制限（最大 200件 / 最大 5回スクロール）を遵守します。
"""

import logging
from typing import Set

from playwright.async_api import Page

import config
from scraper.browser import random_wait

logger = logging.getLogger(__name__)


async def fetch_likers(page: Page, tweet_url: str) -> Set[str]:
    """いいねモーダルから反応者の @screen_name 一覧を取得する。

    ツイートページに遷移済みであることを前提とし、いいね数リンクをクリックして
    モーダルを開き、UserCell 要素から screen_name を抽出します。

    Args:
        page: Playwright の Page オブジェクト（ツイートページ表示済み）。
        tweet_url: 対象ツイートの URL（ページ遷移が必要な場合のフォールバック用）。

    Returns:
        set[str]: 反応者の @screen_name の集合（重複なし）。
    """
    users: Set[str] = set()

    try:
        # 現在のURLがツイートページでなければ遷移
        current_url = page.url
        if "/status/" not in current_url:
            await page.goto(tweet_url, wait_until="domcontentloaded")
            await random_wait()

        # いいね数リンクをクリックしてモーダルを開く
        # href に "/likes" を含むリンクを探す
        likes_link = page.locator("a[href$='/likes']").first
        await likes_link.wait_for(state="visible", timeout=10000)
        await likes_link.click()
        await random_wait()

        # モーダルが表示されるのを待つ
        modal = page.locator("div[aria-modal='true']").first
        await modal.wait_for(state="visible", timeout=10000)

        # スクロールしてユーザーを収集
        scroll_count = 0
        prev_count = 0

        while (
            scroll_count < config.MAX_SCROLL_COUNT
            and len(users) < config.MAX_LIKERS
        ):
            # UserCell 要素からユーザー情報を抽出
            user_cells = modal.locator("[data-testid='UserCell']")
            cell_count = await user_cells.count()

            for i in range(cell_count):
                cell = user_cells.nth(i)
                # UserCell 内のリンクから screen_name を抽出
                # プロフィールリンクは "/@username" の形式
                links = cell.locator("a[role='link']")
                link_count = await links.count()

                for j in range(link_count):
                    link = links.nth(j)
                    href = await link.get_attribute("href")
                    if href and href.startswith("/") and not href.startswith("//"):
                        # "/@username" or "/username" パターン
                        parts = href.strip("/").split("/")
                        if parts and len(parts) == 1:
                            screen_name = f"@{parts[0]}"
                            users.add(screen_name)
                            break  # 1つのUserCellから1つだけ取得

                if len(users) >= config.MAX_LIKERS:
                    break

            # 新しいユーザーが増えなかったら終了
            if len(users) == prev_count and scroll_count > 0:
                logger.info(
                    "新規ユーザーなし、スクロール終了 (count=%d)", len(users)
                )
                break

            prev_count = len(users)

            # モーダル内をスクロール
            await modal.evaluate("node => node.scrollTop = node.scrollHeight")
            scroll_count += 1
            await random_wait()

            logger.debug(
                "スクロール %d/%d 完了, ユーザー数: %d",
                scroll_count,
                config.MAX_SCROLL_COUNT,
                len(users),
            )

        logger.info(
            "いいねモーダルから %d 名のユーザーを取得 (スクロール %d 回)",
            len(users),
            scroll_count,
        )

        # モーダルを閉じる（Escape キー）
        await page.keyboard.press("Escape")
        await random_wait(min_sec=0.5, max_sec=1.5)

    except Exception as e:
        logger.warning("いいねモーダルからの取得に失敗: %s", e)

    return users
