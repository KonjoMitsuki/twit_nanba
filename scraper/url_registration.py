"""Register a specific artwork post using the collector's browser lock/session."""

import asyncio
import logging
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit

import config
from notion_client_wrapper import artworks
from processing.character_mapper import characters_for_tags
from processing.scheduler import calculate_next_schedule
from scraper.auto_detect import _extract_tweet_info, calculate_initial_stage
from storage import app_db, backup_db

logger = logging.getLogger("url_registration")


class RegistrationError(Exception):
    """A registration failure whose message can be shown to the user."""


def normalize_post_url(url: str) -> str:
    """Accept only X post links and remove sharing queries/media suffixes."""
    try:
        parsed = urlsplit(url.strip())
    except ValueError:
        raise ValueError("Xの投稿URLを入力してください。") from None
    match = re.fullmatch(
        r"/([A-Za-z0-9_]{1,15}|i/web)/status/([1-9][0-9]{0,19})"
        r"(?:/(?:photo|video)/[1-4])?/?",
        parsed.path,
    )
    if (
        parsed.scheme not in {"https", "http"}
        or parsed.netloc.lower() not in {
            "x.com", "www.x.com", "mobile.x.com",
            "twitter.com", "www.twitter.com", "mobile.twitter.com",
        }
        or not match
    ):
        raise ValueError("Xの投稿URLを入力してください。")
    return f"https://x.com/{match[1]}/status/{match[2]}"


def _existing_registration(tweet_id: str):
    return artworks.find_by_tweet_id(tweet_id), app_db.find_artwork_by_tweet_id(tweet_id)


def _save_registration(info: dict, notion_page: dict | None, local: dict | None) -> dict:
    posted_at = datetime.fromisoformat(info["post_time_iso"].replace("Z", "+00:00"))
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    stage = calculate_initial_stage(posted_at.isoformat())
    registration = {
        "title": f"作品 ({info['tweet_id']})",
        "url": info["tweet_url"],
        "posted_at": posted_at.isoformat(),
        "status": stage,
        "next_schedule": calculate_next_schedule(posted_at, stage).isoformat(),
        "new_fans_count": 0,
    }
    # Retrying a partial save must preserve the existing tracking progress.
    if notion_page:
        registration.update(artworks.extract_artwork_info(notion_page))
    elif local:
        registration.update({key: local[key] for key in registration})

    if notion_page:
        page_id = notion_page["id"]
    else:
        initial_stage = registration["status"]
        if initial_stage not in config.STAGE_MAP:
            initial_stage = stage
        page_id = artworks.create_artwork_auto(
            url=registration["url"], title=registration["title"],
            posted_at=datetime.fromisoformat(registration["posted_at"]),
            initial_stage=initial_stage, image_urls=info["image_urls"], tags=info["tags"],
        )
        if local:
            next_schedule = registration["next_schedule"]
            artworks.update_status(
                page_id, registration["status"],
                datetime.fromisoformat(next_schedule) if next_schedule else None,
            )

    try:
        artwork_id = local["id"] if local else app_db.upsert_artwork(
            tweet_id=info["tweet_id"], **{key: value for key, value in registration.items() if key != "page_id"},
            image_urls=info["image_urls"], tags=info["tags"],
            characters=characters_for_tags(info["tags"], config.CHARACTER_MAP_PATH),
        )
    except Exception as error:
        raise RegistrationError(
            "Notionには登録済みですが、サイトへの保存に失敗しました。時間をおいて同じURLで再実行してください。"
        ) from error

    try:
        backup_db.backup_artwork({**registration, "page_id": page_id}, db_path=config.BACKUP_DB_PATH)
    except Exception:
        logger.exception("URL登録のバックアップ保存に失敗")
    return {"status": "registered", "artwork_id": artwork_id, "posted_at": registration["posted_at"]}


async def register_post_url(page, url: str, screen_name: str) -> dict:
    url = normalize_post_url(url)
    owner, tweet_id = urlsplit(url).path.rsplit("/status/", 1)
    tracked_name = screen_name.strip().lstrip("@").lower()
    if not tracked_name:
        raise RegistrationError("追跡対象のアカウントが設定されていません。")
    if owner not in {"/i", "/i/web"} and owner[1:].lower() != tracked_name:
        raise RegistrationError("追跡中アカウントの投稿URLを指定してください。")

    notion_page, local = await asyncio.to_thread(_existing_registration, tweet_id)
    if notion_page and local:
        return {"status": "already_registered", "artwork_id": local["id"], "posted_at": local["posted_at"]}

    # A thread may contain replies before the requested post. Match its timestamp link.
    tweet = page.locator("main article[data-testid='tweet']").filter(has=page.locator(
        f"a[href$='/status/{tweet_id}'] time, a[href*='/status/{tweet_id}?'] time"
    )).first
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await tweet.wait_for(state="attached", timeout=config.PROFILE_LOAD_TIMEOUT_SEC * 1000)
        info = await _extract_tweet_info(tweet)
    except Exception as error:
        raise RegistrationError(
            "投稿を読み込めませんでした。URLとXでの公開状態を確認し、時間をおいて再実行してください。"
        ) from error
    if not info or info["tweet_id"] != tweet_id:
        raise RegistrationError("指定した投稿の情報を取得できませんでした。時間をおいて再実行してください。")
    actual_url = normalize_post_url(info["tweet_url"])
    actual_owner = urlsplit(actual_url).path.split("/")[1]
    if actual_owner.lower() != tracked_name:
        raise RegistrationError("追跡中アカウントの投稿URLを指定してください。")
    if not info.get("image_urls"):
        raise RegistrationError("画像付きの投稿URLを指定してください。")
    if not info.get("post_time_iso"):
        raise RegistrationError("投稿日時を取得できませんでした。時間をおいて再実行してください。")
    info["tweet_url"] = actual_url
    return await asyncio.to_thread(_save_registration, info, notion_page, local)
