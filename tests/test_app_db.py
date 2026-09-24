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

    artwork = app_db.get_calendar(2026, 9, db_path)["days"][0]["artworks"][0]

    assert artwork["likes"] is None
    assert artwork["retweets"] is None
