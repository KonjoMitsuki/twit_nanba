import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

import main
from scraper.metrics import PostUnavailableError
from storage import app_db


@pytest.fixture
def collection(monkeypatch, tmp_path):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "app.db"))
    info = {
        "page_id": "notion-artwork",
        "url": "https://x.com/example/status/123456789",
        "title": "Example",
        "posted_at": "2026-10-03T03:00:00+00:00",
        "status": "2h",
        "new_fans_count": 7,
    }
    artwork_id = app_db.upsert_artwork(
        tweet_id="123456789", url=info["url"], title=info["title"],
        posted_at=info["posted_at"], status="2h", new_fans_count=7,
        next_schedule="2026-10-03T05:00:00+00:00",
    )
    app_db.add_metric_snapshot(
        artwork_id, stage="1h", elapsed_seconds=3600,
        measured_at="2026-10-03T04:00:00+00:00",
        impressions=100, likes=10, retweets=2, followers=300,
    )
    snapshot_before = app_db.get_metrics(artwork_id)
    writes = {}
    for module, name in (
        (main.artworks, "update_status"),
        (main.metrics_db, "create_snapshot"),
        (main.backup_db, "backup_metrics"),
        (main.backup_db, "backup_artwork"),
    ):
        writes[name] = Mock(return_value="notion-snapshot")
        monkeypatch.setattr(module, name, writes[name])
    monkeypatch.setattr(main, "random_wait", AsyncMock())
    monkeypatch.setattr(main, "fetch_likers", AsyncMock())
    monkeypatch.setattr(main, "fetch_metrics", AsyncMock(side_effect=PostUnavailableError("投稿を取得できません")))
    return info, artwork_id, snapshot_before, writes


@pytest.mark.parametrize("failed_store", [None, "notion", "sqlite"])
def test_unavailable_post_defers_without_rewriting_metrics_or_stage(collection, monkeypatch, caplog, failed_store):
    info, artwork_id, snapshot_before, writes = collection
    before = datetime.now(timezone.utc)
    if failed_store == "notion":
        writes["update_status"].side_effect = RuntimeError("Notion unavailable")
    elif failed_store == "sqlite":
        monkeypatch.setattr(app_db, "update_artwork", Mock(side_effect=RuntimeError("SQLite unavailable")))

    result = asyncio.run(main.process_artwork(object(), info, set()))

    assert result == set()
    assert app_db.get_metrics(artwork_id) == snapshot_before
    artwork = app_db.get_artwork(artwork_id)
    assert artwork["status"] == "2h"
    assert artwork["new_fans_count"] == 7
    page_id, stage, next_retry = writes["update_status"].call_args.args
    assert (page_id, stage) == ("notion-artwork", "2h")
    retry_delay = timedelta(seconds=main.config.UNAVAILABLE_POST_RETRY_SEC)
    assert before + retry_delay <= next_retry <= datetime.now(timezone.utc) + retry_delay
    assert next_retry.tzinfo is timezone.utc
    if failed_store != "sqlite":
        assert artwork["next_schedule"] == next_retry.isoformat()
    if failed_store:
        assert "再確認予定の保存失敗" in caplog.text
    assert "数値取得タイムアウト" not in caplog.text
    for name in ("create_snapshot", "backup_metrics", "backup_artwork"):
        writes[name].assert_not_called()
    main.fetch_likers.assert_not_awaited()


def test_collection_resumes_at_same_stage_when_post_becomes_available(collection):
    info, artwork_id, snapshot_before, writes = collection
    asyncio.run(main.process_artwork(object(), info, set()))
    main.fetch_metrics.side_effect = None
    main.fetch_metrics.return_value = {
        "impressions": 200, "likes": 20, "retweets": 3, "followers": 321,
    }

    asyncio.run(main.process_artwork(object(), info, set()))

    snapshots = app_db.get_metrics(artwork_id)
    assert snapshots[0] == snapshot_before[0]
    assert snapshots[1]["stage"] == "2h"
    assert snapshots[1]["likes"] == 20
    assert app_db.get_artwork(artwork_id)["status"] == "3h"
    assert writes["create_snapshot"].call_args.kwargs["stage"] == "2h"


def test_actual_timeout_keeps_stage_and_retry_schedule(collection):
    info, artwork_id, snapshot_before, writes = collection
    main.fetch_metrics.side_effect = TimeoutError("No response")

    result = asyncio.run(main.process_artwork(object(), info, set()))

    assert result == set()
    artwork = app_db.get_artwork(artwork_id)
    assert artwork["status"] == "2h"
    assert artwork["next_schedule"] == "2026-10-03T05:00:00+00:00"
    assert app_db.get_metrics(artwork_id) == snapshot_before
    for write in writes.values():
        write.assert_not_called()
