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


def test_register_artwork_main_passes_character(monkeypatch):
    captured_kwargs = {}

    monkeypatch.setattr(
        "sys.argv",
        [
            "register_artwork.py",
            "https://x.com/user/status/123456789",
            "--title",
            "テスト作品",
            "--character",
            "初音ミク",
        ],
    )

    async def fake_fetch(_url):
        return {"image_urls": [], "tags": [], "post_time_iso": "2026-09-01T12:00:00+00:00"}

    monkeypatch.setattr(register_artwork, "fetch_tweet_info", fake_fetch)
    monkeypatch.setattr(register_artwork.artworks, "find_by_tweet_url", lambda _url: {"id": "page-123"})

    def fake_upsert(**kwargs):
        captured_kwargs.update(kwargs)
        return "art_123"

    monkeypatch.setattr(register_artwork.app_db, "upsert_artwork", fake_upsert)

    register_artwork.main()

    assert captured_kwargs["character"] == "初音ミク"
    assert captured_kwargs["title"] == "テスト作品"


def test_register_artwork_main_fills_character_from_tags(monkeypatch, tmp_path):
    captured_kwargs = {}
    mapping_path = tmp_path / "character_map.csv"
    mapping_path.write_text("tag,character\n初音ミク,初音ミク\n", encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["register_artwork.py", "https://x.com/user/status/123456789"],
    )
    monkeypatch.setattr(register_artwork.config, "CHARACTER_MAP_PATH", str(mapping_path))
    monkeypatch.setattr(
        register_artwork,
        "fetch_tweet_info",
        lambda _url: None,
    )

    async def fake_fetch(_url):
        return {"image_urls": [], "tags": ["初音ミク"], "post_time_iso": "2026-09-01T12:00:00+00:00"}

    monkeypatch.setattr(register_artwork, "fetch_tweet_info", fake_fetch)
    monkeypatch.setattr(register_artwork.artworks, "find_by_tweet_url", lambda _url: {"id": "page-123"})
    monkeypatch.setattr(register_artwork.app_db, "upsert_artwork", lambda **kwargs: captured_kwargs.update(kwargs) or "art_123")

    register_artwork.main()

    assert captured_kwargs["character"] == "初音ミク"