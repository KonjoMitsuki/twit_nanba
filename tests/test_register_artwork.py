from datetime import datetime, timezone

import register_artwork
from register_artwork import fetch_syndicated_tweet_info, tweet_id_to_posted_at


def test_tweet_id_to_posted_at_decodes_x_snowflake_timestamp():
    posted_at = tweet_id_to_posted_at("2103824446700278159")

    assert posted_at == datetime(
        2026, 9, 26, 12, 30, 9, 918000, tzinfo=timezone.utc
    )
    assert posted_at.tzinfo == timezone.utc


def test_fetch_syndicated_tweet_info_uses_token_and_parses_iso_timestamp(monkeypatch):
    captured_params = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "created_at": "2026-09-26T12:30:09.000Z",
                "mediaDetails": [
                    {
                        "type": "photo",
                        "media_url_https": "https://pbs.twimg.com/media/test.jpg",
                    },
                ],
                "text": "#test",
            }

    def fake_get(_url, *, params, headers, timeout):
        captured_params.update(params)
        return FakeResponse()

    monkeypatch.setattr(register_artwork.httpx, "get", fake_get)

    info = fetch_syndicated_tweet_info(
        "https://x.com/user/status/2103824446700278159"
    )

    assert captured_params["token"] > 0
    assert info["post_time_iso"] == "2026-09-26T12:30:09+00:00"
    assert info["image_urls"] == ["https://pbs.twimg.com/media/test.jpg"]