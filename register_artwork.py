"""
register_artwork.py — 新規作品登録 CLI

ツイート URL を指定して作品マスターDB に新規エントリを作成します。
初回ステータスは "5m"、次回予定は posted_at + 5分に設定されます。

使い方:
    python register_artwork.py <TWEET_URL> [--title TITLE] [--posted-at ISO_DATETIME]

例:
    python register_artwork.py "https://x.com/user/status/123456789" \\
        --title "夏のイラスト" \\
        --posted-at "2026-08-18T21:00:00+09:00"

    # --posted-at を省略すると現在時刻が使われます
    python register_artwork.py "https://x.com/user/status/123456789"
"""

import argparse
import asyncio
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx

from notion_client_wrapper import artworks
from scraper.browser import create_browser_context
from scraper.auto_detect import _extract_tweet_info
from storage import app_db


def normalize_tweet_url(url: str) -> str:
    """X投稿URLからクエリとフラグメントを除いた正規URLを返す。"""
    parsed = urlsplit(url.strip())
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", ""))


async def fetch_tweet_info(url: str) -> dict:
    """認証済みXページから投稿画像と投稿日時を取得する。"""
    try:
        async with create_browser_context(headless=True) as (_context, page):
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_selector(
                "article[data-testid='tweet']",
                state="visible",
                timeout=30000,
            )
            tweet = page.locator("article[data-testid='tweet']").first
            tweet_info = await _extract_tweet_info(tweet)
            if tweet_info is not None:
                return tweet_info
    except Exception:
        pass

    # Xのログイン画面・レート制限時は、公開シンジケーション情報を試す。
    return fetch_syndicated_tweet_info(url)


def fetch_syndicated_tweet_info(url: str) -> dict:
    """投稿IDから公開情報を取得し、手動登録に必要な画像を抽出する。"""
    match = re.search(r"/status/(\d+)", urlsplit(url).path)
    if match is None:
        raise RuntimeError("投稿IDをURLから取得できませんでした")

    tweet_id = match.group(1)
    response = httpx.get(
        "https://cdn.syndication.twimg.com/tweet-result",
        params={"id": tweet_id, "lang": "ja"},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    image_urls = [
        media["media_url_https"]
        for media in payload.get("mediaDetails", [])
        if media.get("type") == "photo" and media.get("media_url_https")
    ]
    post_time = payload.get("created_at")
    posted_at = parsedate_to_datetime(post_time) if post_time else None
    return {
        "tweet_id": tweet_id,
        "tweet_url": normalize_tweet_url(url),
        "post_time_iso": posted_at.isoformat() if posted_at else None,
        "image_urls": image_urls,
        "tags": re.findall(r"#([\wぁ-んァ-ヶ一-龯々ー]+)", payload.get("text", "")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="新規イラスト作品をNotionに登録します。",
    )
    parser.add_argument(
        "url",
        type=str,
        help="ツイートの直リンク URL（例: https://x.com/user/status/123456789）",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="作品名。省略時はツイートURLの末尾IDが使われます。",
    )
    parser.add_argument(
        "--posted-at",
        type=str,
        default=None,
        help="投稿日時（ISO 8601形式）。省略時は現在時刻。",
    )

    args = parser.parse_args()

    # URL バリデーション
    original_url: str = args.url.strip()
    url: str = normalize_tweet_url(original_url)
    if "status/" not in url:
        print("エラー: 有効なツイートURLを指定してください。", file=sys.stderr)
        print("例: https://x.com/user/status/123456789", file=sys.stderr)
        sys.exit(1)

    # タイトル
    title: str = args.title or f"作品 ({url.split('/')[-1]})"

    # 投稿日時
    if args.posted_at:
        try:
            posted_at = datetime.fromisoformat(args.posted_at)
        except ValueError:
            print(
                "エラー: --posted-at は ISO 8601 形式で指定してください。",
                file=sys.stderr,
            )
            print("例: 2026-08-18T21:00:00+09:00", file=sys.stderr)
            sys.exit(1)
    else:
        posted_at = datetime.now(timezone.utc)

    # タイムゾーン情報がなければ UTC として扱う
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    # Web UIでも画像を表示できるよう、認証済みXページから画像URLを取得する。
    try:
        tweet_info = asyncio.run(fetch_tweet_info(url))
        image_urls = tweet_info.get("image_urls", [])
        tags = tweet_info.get("tags", [])
        if not args.posted_at and tweet_info.get("post_time_iso"):
            posted_at = datetime.fromisoformat(
                tweet_info["post_time_iso"].replace("Z", "+00:00")
            )
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
    except Exception as e:
        print(f"⚠️ Xページから画像を取得できませんでした: {e}", file=sys.stderr)
        image_urls = []
        tags = []

    # Notion に登録（同じURLの再実行では重複ページを作らない）
    try:
        existing_page = artworks.find_by_tweet_url(url)
        if existing_page is None and original_url != url:
            existing_page = artworks.find_by_tweet_url(original_url)
        if existing_page:
            page_id = existing_page["id"]
            print("ℹ️ Notionには既に登録済みです。重複登録をスキップしました。")
        else:
            page_id = artworks.create_artwork(
                url=url,
                title=title,
                posted_at=posted_at,
                image_urls=image_urls,
                tags=tags,
            )
            print("✅ 作品を登録しました。")
        print(f"   タイトル: {title}")
        print(f"   URL: {url}")
        print(f"   投稿日時: {posted_at.isoformat()}")
        print(f"   Page ID: {page_id}")
        print(f"   ステータス: 5m（初回計測待ち）")
    except Exception as e:
        print(f"❌ 登録に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        app_id = app_db.upsert_artwork(
            tweet_id=url.rstrip("/").split("/")[-1],
            url=url,
            title=title,
            posted_at=posted_at.isoformat(),
            status="5m",
            image_urls=image_urls,
            tags=tags,
        )
        print(f"✅ App DB にも登録しました: {app_id}")
    except Exception as e:
        print(f"⚠️ App DB への登録に失敗しました（Notion 登録は成功）: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
