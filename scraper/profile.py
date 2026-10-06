"""X プロフィールからアカウント情報を取得する。"""

import logging
import re

from playwright.async_api import Page

logger = logging.getLogger(__name__)


def parse_follower_count(value: str | None) -> int | None:
    """X の表示形式（例: ``1,234``、``12.3万``）を整数へ変換する。"""
    if not value:
        return None

    normalized = value.replace(",", "").replace(" ", "")
    match = re.search(r"(\d+(?:\.\d+)?)(万|千|K|M)?", normalized, re.IGNORECASE)
    if match is None:
        return None

    number = float(match.group(1))
    unit = (match.group(2) or "").lower()
    multiplier = {"万": 10000, "千": 1000, "k": 1000, "m": 1000000}.get(unit, 1)
    return int(number * multiplier)


def _extract_from_texts(texts: list[str]) -> int | None:
    for text in texts:
        if re.search(r"フォロワー|followers?", text, re.IGNORECASE):
            count = parse_follower_count(text)
            if count is not None:
                return count
    return None


async def fetch_profile_followers(page: Page, screen_name: str) -> int | None:
    """表示中のプロフィールからフォロワー数を取得する。"""
    del screen_name  # URL 遷移はプロフィール確認側が担当する。

    follower_link = page.locator("a[href$='/followers']").first
    if await follower_link.count() > 0:
        texts = [
            await follower_link.inner_text(),
            await follower_link.get_attribute("aria-label") or "",
        ]
        count = _extract_from_texts(texts)
        if count is not None:
            return count

    texts: list[str] = []
    for locator in (
        page.locator("[aria-label*='フォロワー']"),
        page.locator("[aria-label*='Followers']"),
    ):
        for index in range(await locator.count()):
            texts.append(await locator.nth(index).get_attribute("aria-label") or "")

    count = _extract_from_texts(texts)
    if count is not None:
        return count

    profile_text = await page.locator("main").inner_text()
    count = _extract_from_texts(profile_text.splitlines())
    if count is None:
        logger.warning("プロフィールからフォロワー数を取得できませんでした")
    return count