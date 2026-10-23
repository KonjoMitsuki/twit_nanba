from processing.character_mapper import match_characters
from storage import app_db


def test_calendar_uses_jst_date_and_daily_follower_delta(tmp_path):
    db_path = str(tmp_path / "app.db")
    artwork_id = app_db.create_artwork(
        tweet_id="tweet-1",
        url="https://x.com/example/status/1",
        title="JST boundary",
        posted_at="2026-08-31T15:30:00+00:00",
        db_path=db_path,
    )
    app_db.add_account_metric(100, "2026-08-31T14:00:00+00:00", db_path)
    app_db.add_account_metric(121, "2026-09-01T14:30:00+00:00", db_path)
    app_db.add_metric_snapshot(
        artwork_id,
        stage="5m",
        elapsed_seconds=300,
        measured_at="2026-08-31T15:35:00+00:00",
        likes=4,
        db_path=db_path,
    )

    result = app_db.get_calendar(2026, 9, db_path)

    assert result["summary"]["posts"] == 1
    assert result["days"][0]["date"] == "2026-09-01"
    assert result["days"][0]["followers_delta"] == 21


def test_backfill_account_metrics_is_idempotent_and_ignores_invalid_values(tmp_path):
    db_path = str(tmp_path / "app.db")
    artwork_id = app_db.create_artwork(
        tweet_id="tweet-backfill",
        url="https://x.com/example/status/backfill",
        title="Backfill",
        posted_at="2026-08-31T12:00:00+00:00",
        db_path=db_path,
    )
    app_db.add_metric_snapshot(
        artwork_id,
        stage="5m",
        elapsed_seconds=300,
        measured_at="2026-08-31T12:05:00+00:00",
        followers=100,
        db_path=db_path,
    )
    app_db.add_metric_snapshot(
        artwork_id,
        stage="1h",
        elapsed_seconds=3600,
        measured_at="2026-08-31T13:00:00+00:00",
        followers=0,
        db_path=db_path,
    )

    first = app_db.backfill_account_metrics_from_snapshots(db_path)
    second = app_db.backfill_account_metrics_from_snapshots(db_path)

    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert app_db.get_followers(
        "2026-08-31T12:00:00+00:00",
        "2026-08-31T14:00:00+00:00",
        db_path,
    )[0]["followers"] == 100


def test_missing_latest_metric_is_not_zero(tmp_path):
    db_path = str(tmp_path / "app.db")
    app_db.create_artwork(
        tweet_id="tweet-2",
        url="https://x.com/example/status/2",
        title="No measurements",
        posted_at="2026-09-10T12:00:00+00:00",
        db_path=db_path,
    )

    days = app_db.get_calendar(2026, 9, db_path)["days"]
    artwork = next(day["artworks"][0] for day in days if day["artworks"])

    assert artwork["likes"] is None
    assert artwork["retweets"] is None


def test_calendar_returns_every_day_and_independent_follower_delta(tmp_path):
    db_path = str(tmp_path / "app.db")
    artwork_id = app_db.create_artwork(
        tweet_id="tweet-3",
        url="https://x.com/example/status/3",
        title="August work",
        posted_at="2026-08-03T12:00:00+00:00",
        db_path=db_path,
    )
    app_db.add_account_metric(100, "2026-07-31T14:00:00+00:00", db_path)
    app_db.add_account_metric(100, "2026-08-01T14:00:00+00:00", db_path)
    app_db.add_account_metric(110, "2026-08-02T03:00:00+00:00", db_path)
    app_db.add_account_metric(121, "2026-08-03T14:00:00+00:00", db_path)
    app_db.add_account_metric(130, "2026-09-01T00:00:00+00:00", db_path)
    app_db.add_metric_snapshot(artwork_id, stage="5m", elapsed_seconds=300, measured_at="2026-08-03T12:05:00+00:00", likes=8, db_path=db_path)

    result = app_db.get_calendar(2026, 8, db_path)
    days = {day["date"]: day for day in result["days"]}

    assert len(result["days"]) == 31
    assert days["2026-08-02"]["artworks"] == []
    assert days["2026-08-02"]["followers_delta"] == 10
    assert days["2026-08-03"]["artworks"][0]["id"] == artwork_id
    assert result["summary"]["followers"] == 121
    assert result["summary"]["followers_delta"] == 21


def test_calendar_daily_delta_is_none_without_prior_measurement(tmp_path):
    db_path = str(tmp_path / "app.db")
    app_db.add_account_metric(121, "2026-08-03T14:00:00+00:00", db_path)

    result = app_db.get_calendar(2026, 8, db_path)

    assert result["days"][2]["followers_delta"] is None


def test_artwork_images_and_metrics_are_ordered(tmp_path):
    db_path = str(tmp_path / "app.db")
    artwork_id = app_db.create_artwork(
        tweet_id="tweet-4",
        url="https://x.com/example/status/4",
        title="Ordered work",
        posted_at="2026-08-04T12:00:00+00:00",
        image_urls=["https://example.com/1.jpg", "https://example.com/2.jpg", "https://example.com/3.jpg", "https://example.com/4.jpg"],
        db_path=db_path,
    )
    app_db.add_metric_snapshot(artwork_id, stage="1h", elapsed_seconds=3600, measured_at="2026-08-04T13:00:00+00:00", likes=20, db_path=db_path)
    app_db.add_metric_snapshot(artwork_id, stage="5m", elapsed_seconds=300, measured_at="2026-08-04T12:05:00+00:00", likes=5, db_path=db_path)

    artwork = app_db.get_artwork(artwork_id, db_path)

    assert [image["image_order"] for image in artwork["images"]] == [1, 2, 3, 4]
    assert [point["elapsed_seconds"] for point in app_db.get_metrics(artwork_id, db_path)] == [300, 3600]


def test_artwork_character_crud_and_migration(tmp_path):
    db_path = str(tmp_path / "app.db")

    # 1. create_artwork with character
    artwork_id = app_db.create_artwork(
        tweet_id="tweet-char-1",
        url="https://x.com/example/status/char1",
        title="Character Test 1",
        posted_at="2026-09-01T12:00:00+00:00",
        character="初音ミク",
        db_path=db_path,
    )
    artwork = app_db.get_artwork(artwork_id, db_path)
    assert artwork["character"] == "初音ミク"

    # 2. get_calendar includes character
    cal = app_db.get_calendar(2026, 9, db_path)
    day = next(d for d in cal["days"] if d["date"] == "2026-09-01")
    assert day["artworks"][0]["character"] == "初音ミク"

    # 3. update_artwork updates character
    app_db.update_artwork(artwork_id, character="巡音ルカ", db_path=db_path)
    artwork = app_db.get_artwork(artwork_id, db_path)
    assert artwork["character"] == "巡音ルカ"

    # 4. upsert_artwork retains existing character if not provided, updates if provided
    app_db.upsert_artwork(
        tweet_id="tweet-char-1",
        url="https://x.com/example/status/char1",
        title="Character Test 1 Updated",
        posted_at="2026-09-01T12:00:00+00:00",
        character=None,
        db_path=db_path,
    )
    artwork = app_db.get_artwork(artwork_id, db_path)
    assert artwork["character"] == "巡音ルカ"

    app_db.upsert_artwork(
        tweet_id="tweet-char-1",
        url="https://x.com/example/status/char1",
        title="Character Test 1 Updated Again",
        posted_at="2026-09-01T12:00:00+00:00",
        character="鏡音リン",
        db_path=db_path,
    )
    artwork = app_db.get_artwork(artwork_id, db_path)
    assert artwork["character"] == "鏡音リン"


def test_auto_fill_missing_characters_scans_all_and_protects_manual(tmp_path):
    db_path = str(tmp_path / "app.db")
    mapping = {"miku": "初音ミク", "luka": "巡音ルカ"}

    def create(tweet_id, *, tags, **kwargs):
        return app_db.create_artwork(
            tweet_id=tweet_id,
            url=f"https://x.com/example/status/{tweet_id}",
            title=f"Artwork {tweet_id}",
            posted_at="2026-09-01T12:00:00+00:00",
            tags=tags,
            db_path=db_path,
            **kwargs,
        )

    matched = create("1", tags=["#MIKU", "Luka"])
    unmatched = create("2", tags=["unknown"])
    manual_empty = create("3", tags=["miku"], characters=[], character_manual=True)
    manual_named = create("4", tags=["luka"], character="手動", character_manual=True)
    existing = create("5", tags=["miku"], character="既存")

    def resolve(tags):
        return match_characters(tags, mapping)

    dry_run = app_db.auto_fill_missing_characters(resolve, db_path, dry_run=True)
    assert dry_run["dry_run"] is True
    assert dry_run["scanned"] == 5
    assert dry_run["skipped_manual"] == 2
    assert dry_run["skipped_existing"] == 1
    assert dry_run["unmatched"] == 1
    assert dry_run["filled"] == 0
    assert dry_run["would_fill"] == 1
    assert dry_run["changes"] == [
        {"id": matched, "title": "Artwork 1", "characters": ["初音ミク", "巡音ルカ"]},
    ]
    assert app_db.get_artwork(matched, db_path)["characters"] == []

    result = app_db.auto_fill_missing_characters(resolve, db_path)
    assert result["dry_run"] is False
    assert result["filled"] == 1
    assert result["would_fill"] == 0
    assert app_db.get_artwork(matched, db_path)["characters"] == ["初音ミク", "巡音ルカ"]
    assert app_db.get_artwork(unmatched, db_path)["characters"] == []
    assert app_db.get_artwork(manual_empty, db_path)["characters"] == []
    assert app_db.get_artwork(manual_named, db_path)["characters"] == ["手動"]
    assert app_db.get_artwork(existing, db_path)["characters"] == ["既存"]

    again = app_db.auto_fill_missing_characters(resolve, db_path)
    assert again["filled"] == 0
    assert again["unmatched"] == 1
    assert again["changes"] == []


def test_init_db_migrates_table_without_character_column(tmp_path):
    import sqlite3
    db_path = str(tmp_path / "legacy.db")

    # Old schema without character column
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
        CREATE TABLE artworks (
            id TEXT PRIMARY KEY,
            tweet_id TEXT NOT NULL UNIQUE,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            posted_at TEXT NOT NULL,
            status TEXT NOT NULL,
            next_schedule TEXT,
            new_fans_count INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)

    # Running init_db will automatically ALTER TABLE to add character column
    app_db.init_db(db_path)

    with sqlite3.connect(db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(artworks)").fetchall()]
    assert "character" in columns
