import config
from notion_client_wrapper import schedule_queue
from scraper.poster import _extract_hashtags, _get_compose_input_selectors


def test_extract_hashtags_from_text():
    text = "#art #pixelart テスト本文 #daily #anime"
    assert _extract_hashtags(text) == ["art", "pixelart", "daily", "anime"]


def test_extract_scheduled_post_info_extracts_title_text_and_images():
    page = {
        "id": "page-123",
        "properties": {
            config.SQ_PROP_TITLE: {"title": [{"plain_text": "予約投稿タイトル"}]},
            config.SQ_PROP_TEXT: {
                "rich_text": [
                    {"plain_text": "本文1"},
                    {"plain_text": "\n本文2"},
                ]
            },
            config.SQ_PROP_ATTACHMENTS: {
                "files": [
                    {"type": "external", "external": {"url": "https://example.com/a.jpg"}},
                    {"type": "file", "file": {"url": "https://example.com/b.jpg"}},
                ]
            },
            config.SQ_PROP_SCHEDULED_AT: {"date": {"start": "2026-09-01T12:00:00+00:00"}},
        },
    }

    result = schedule_queue.extract_scheduled_post_info(page)

    assert result["page_id"] == "page-123"
    assert result["title"] == "予約投稿タイトル"
    assert result["text"] == "本文1\n本文2"
    assert result["image_urls"] == [
        "https://example.com/a.jpg",
        "https://example.com/b.jpg",
    ]
    assert result["scheduled_at"] == "2026-09-01T12:00:00+00:00"


def test_get_due_scheduled_posts_returns_empty_when_db_not_configured(monkeypatch):
    monkeypatch.setattr(config, "SCHEDULE_QUEUE_DB_ID", "")
    assert schedule_queue.get_due_scheduled_posts() == []


def test_compose_input_selectors_include_fallbacks():
    selectors = _get_compose_input_selectors()
    assert "div[data-testid=\"tweetTextarea_0\"]" in selectors
    assert any("role=\"textbox\"" in selector for selector in selectors)
    assert any("textarea" in selector for selector in selectors)
