from datetime import datetime, timezone

from register_artwork import tweet_id_to_posted_at


def test_tweet_id_to_posted_at_decodes_x_snowflake_timestamp():
    posted_at = tweet_id_to_posted_at("2103824446700278159")

    assert posted_at == datetime(
        2026, 9, 26, 12, 30, 9, 918000, tzinfo=timezone.utc
    )
    assert posted_at.tzinfo == timezone.utc