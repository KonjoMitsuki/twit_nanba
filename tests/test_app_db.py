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
