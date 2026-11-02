import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

import config
from notion_client_wrapper import artworks
from scraper import url_registration as registration
from storage import app_db

TWEET_ID = "2116865529227128937"
URL = f"https://x.com/example/status/{TWEET_ID}"


@pytest.mark.parametrize("url", [
    URL, URL + "?s=20#share", URL + "/photo/2", URL + "/",
    URL.replace("x.com", "twitter.com"), URL.replace("x.com", "mobile.twitter.com"),
])
def test_normalize_post_url(url):
    assert registration.normalize_post_url(url) == URL


@pytest.mark.parametrize("url", [
    "", "https://x.com/example", "https://example.com/example/status/123",
    "https://x.com.evil.test/example/status/123", "https://x.com@evil.test/a/status/123",
    "file:///example/status/123", "https://x.com:443/example/status/123",
    "https://x.com/example/status/123/other", "https://x.com/example/status/0",
])
def test_normalize_rejects_non_post_urls(url):
    with pytest.raises(ValueError):
        registration.normalize_post_url(url)


def notion_page(info, *, stage="15m", next_schedule=None):
    return {
        "id": "notion-page", "properties": {
            config.AW_PROP_URL: {"url": info["tweet_url"]},
            config.AW_PROP_TITLE: {"title": [{"plain_text": "Existing title"}]},
            config.AW_PROP_POSTED_AT: {"date": {"start": info["post_time_iso"]}},
            config.AW_PROP_STATUS: {"select": {"name": stage}},
            config.AW_PROP_NEXT_SCHEDULE: {"date": {"start": next_schedule} if next_schedule else None},
            config.AW_PROP_NEW_FANS_COUNT: {"number": 17},
        },
    }


@pytest.fixture
def isolated_registration(monkeypatch, tmp_path):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "app.db"))
    monkeypatch.setattr(config, "BACKUP_DB_PATH", str(tmp_path / "backup.db"))
    mapping = tmp_path / "characters.csv"
    mapping.write_text("tag,character\nmiku,初音ミク\n", encoding="utf-8")
    monkeypatch.setattr(config, "CHARACTER_MAP_PATH", str(mapping))
    stored = []
    find = Mock(side_effect=lambda _tweet_id: stored[0] if stored else None)

    def create(**kwargs):
        info = {"tweet_url": kwargs["url"], "post_time_iso": kwargs["posted_at"].isoformat()}
        stored.append(notion_page(info, stage=kwargs["initial_stage"]))
        return stored[-1]["id"]

    create_mock = Mock(side_effect=create)
    monkeypatch.setattr(artworks, "find_by_tweet_id", find)
    monkeypatch.setattr(artworks, "create_artwork_auto", create_mock)
    monkeypatch.setattr(artworks, "update_status", Mock())
    info = {
        "tweet_id": TWEET_ID, "tweet_url": URL,
        "post_time_iso": (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat(),
        "image_urls": ["https://pbs.twimg.com/media/one.jpg", "https://pbs.twimg.com/media/two.png"],
        "tags": ["miku"],
    }
    monkeypatch.setattr(registration, "_extract_tweet_info", AsyncMock(side_effect=lambda _tweet: dict(info)))
    target = Mock(wait_for=AsyncMock())
    page = Mock(goto=AsyncMock())
    page.locator.return_value.filter.return_value.first = target
    return info, page, stored, create_mock


def run_registration(page, url=URL):
    return asyncio.run(registration.register_post_url(page, url, "@Example"))


def test_url_add_preserves_images_tags_schedule_without_measuring(isolated_registration):
    info, page, _stored, create = isolated_registration
    result = run_registration(page, URL + "?s=20")
    artwork = app_db.get_artwork(result["artwork_id"])
    assert result["status"] == "registered"
    assert artwork["status"] == "15m"
    assert artwork["posted_at"] == info["post_time_iso"]
    assert datetime.fromisoformat(artwork["next_schedule"]) == datetime.fromisoformat(info["post_time_iso"]) + timedelta(minutes=15)
    assert [image["source_url"] for image in artwork["images"]] == info["image_urls"]
    assert artwork["tags"] == ["miku"]
    assert artwork["characters"] == ["初音ミク"]
    assert app_db.get_metrics(result["artwork_id"]) == []
    create.assert_called_once()
    page.goto.assert_awaited_once_with(URL, wait_until="domcontentloaded")


def test_duplicate_keeps_progress_manual_character_and_snapshots(isolated_registration):
    _info, page, _stored, create = isolated_registration
    first = run_registration(page)
    app_db.update_artwork(first["artwork_id"], status="COMPLETED", new_fans_count=9, character="手動指定", character_manual=True)
    app_db.add_metric_snapshot(first["artwork_id"], stage="48h", elapsed_seconds=172800,
                               measured_at=datetime.now(timezone.utc).isoformat(), likes=123)
    before = app_db.get_artwork(first["artwork_id"])
    page.goto.reset_mock()
    result = run_registration(page, URL.replace("x.com", "twitter.com") + "/photo/1?s=20")
    assert result["status"] == "already_registered"
    assert app_db.get_artwork(first["artwork_id"]) == before
    create.assert_called_once()
    page.goto.assert_not_awaited()


@pytest.mark.parametrize("change, message", [
    ({"image_urls": []}, "画像付き"),
    ({"tweet_id": "999"}, "指定した投稿"),
    ({"tweet_url": URL.replace("example", "other")}, "追跡中"),
    ({"post_time_iso": None}, "投稿日時"),
])
def test_invalid_post_is_not_registered(isolated_registration, change, message):
    info, page, _stored, create = isolated_registration
    info.update(change)
    with pytest.raises(registration.RegistrationError, match=message):
        run_registration(page)
    create.assert_not_called()
    assert app_db.find_artwork_by_tweet_id(TWEET_ID) is None


def test_load_failure_and_other_account_have_no_writes(isolated_registration):
    _info, page, _stored, create = isolated_registration
    with pytest.raises(registration.RegistrationError, match="追跡中"):
        run_registration(page, URL.replace("example", "other"))
    page.goto.assert_not_awaited()
    page.goto.side_effect = TimeoutError("private debug info")
    with pytest.raises(registration.RegistrationError, match="読み込めません"):
        run_registration(page)
    create.assert_not_called()


def test_retry_after_local_failure_reuses_notion_progress(isolated_registration, monkeypatch):
    info, page, stored, create = isolated_registration
    original_upsert = app_db.upsert_artwork
    monkeypatch.setattr(app_db, "upsert_artwork", Mock(side_effect=RuntimeError("disk error")))
    with pytest.raises(registration.RegistrationError, match="Notionには登録済み"):
        run_registration(page)
    retry_at = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    stored[0] = notion_page(info, stage="2h", next_schedule=retry_at)
    monkeypatch.setattr(app_db, "upsert_artwork", original_upsert)
    result = run_registration(page)
    saved = app_db.get_artwork(result["artwork_id"])
    assert saved["status"] == "2h"
    assert saved["next_schedule"] == retry_at
    assert saved["new_fans_count"] == 17
    assert saved["title"] == "Existing title"
    create.assert_called_once()


def test_notion_failure_can_retry_without_local_orphan(isolated_registration):
    _info, page, _stored, create = isolated_registration
    create.side_effect = RuntimeError("Notion unavailable")
    with pytest.raises(RuntimeError, match="Notion unavailable"):
        run_registration(page)
    assert app_db.find_artwork_by_tweet_id(TWEET_ID) is None


def test_local_only_registration_preserves_completed_state(isolated_registration):
    info, page, _stored, create = isolated_registration
    artwork_id = app_db.create_artwork(
        tweet_id=TWEET_ID, url=URL, title="Local title", posted_at=info["post_time_iso"],
        status="COMPLETED", character="手動指定", character_manual=True,
    )
    before = app_db.get_artwork(artwork_id)
    result = run_registration(page)
    assert result["artwork_id"] == artwork_id
    assert app_db.get_artwork(artwork_id) == before
    create.assert_called_once()
    artworks.update_status.assert_called_once_with("notion-page", "COMPLETED", None)


@pytest.mark.parametrize("path", ["i/status", "i/web/status"])
def test_id_only_links_resolve_and_verify_real_author(isolated_registration, path):
    _info, page, _stored, create = isolated_registration
    assert run_registration(page, f"https://x.com/{path}/{TWEET_ID}")["status"] == "registered"
    assert create.call_args.kwargs["url"] == URL


def test_old_post_uses_last_configured_stage_without_changing_profile_gate(isolated_registration, monkeypatch, tmp_path):
    info, page, _stored, _create = isolated_registration
    info["post_time_iso"] = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    state_file = tmp_path / "last-profile-check"
    state_file.write_text("unchanged")
    monkeypatch.setattr(config, "AUTO_DETECT_STATE_FILE", str(state_file))
    result = run_registration(page)
    assert app_db.get_artwork(result["artwork_id"])["status"] == config.SCHEDULE_STAGES[-1]["name"]
    assert state_file.read_text() == "unchanged"


def test_notion_id_lookup_handles_variants_pagination_and_id_prefixes(monkeypatch):
    def entry(url):
        return {"id": url, "properties": {config.AW_PROP_URL: {"url": url}}}

    target = entry("https://twitter.com/example/status/123?s=20")
    client = Mock()
    client.request.side_effect = [
        {"results": [entry("https://x.com/example/status/1234")], "has_more": True, "next_cursor": "next"},
        {"results": [target], "has_more": False},
    ]
    monkeypatch.setattr(artworks, "get_client", lambda: client)
    assert artworks.find_by_tweet_id("123") == target
    assert client.request.call_count == 2
    assert client.request.call_args.kwargs["body"]["start_cursor"] == "next"
