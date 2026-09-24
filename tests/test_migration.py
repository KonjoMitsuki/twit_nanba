from scripts import migrate_notion_to_app_db as migration
from storage import app_db


class FakeNotion:
    def __init__(self):
        self.pages = {
            "artworks": [{
                "id": "notion-art-1",
                "properties": {
                    "作品名": {"title": [{"plain_text": "移行作品"}]},
                    "URL": {"url": "https://x.com/me/status/123"},
                    "投稿日時": {"date": {"start": "2026-09-01T12:00:00+00:00"}},
                    "ステータス": {"select": {"name": "5m"}},
                    "次回予定": {"date": {"start": "2026-09-01T12:05:00+00:00"}},
                    "はじめて反応した人の数": {"number": 2},
                    "画像": {"files": [{"type": "external", "external": {"url": "https://example.com/a.jpg"}}]},
                    "タグ": {"multi_select": [{"name": "art"}]},
                },
            }],
            "metrics": [{
                "id": "notion-metric-1",
                "properties": {
                    "親ツイート": {"relation": [{"id": "notion-art-1"}]},
                    "経過時間": {"select": {"name": "5m"}},
                    "計測日時": {"date": {"start": "2026-09-01T12:05:00+00:00"}},
                    "Impressions": {"number": 100},
                    "Likes": {"number": 10},
                    "Retweets": {"number": 2},
                    "Followers": {"number": 50},
                    "New Fans": {"number": 1},
                },
            }],
        }

    def request(self, path, method, body):
        return {"results": self.pages["metrics" if "METRICS" in path else "artworks"], "has_more": False}


def test_migration_is_idempotent(monkeypatch, tmp_path):
    db_path = str(tmp_path / "app.db")
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    monkeypatch.setattr(migration, "get_client", lambda: FakeNotion())
    monkeypatch.setattr(migration.config, "ARTWORKS_DB_ID", "ARTWORKS")
    monkeypatch.setattr(migration.config, "METRICS_DB_ID", "METRICS")

    first = migration.migrate()
    second = migration.migrate()

    assert first["artworks_inserted"] == 1
    assert first["metrics_inserted"] == 1
    assert second["artworks_skipped"] == 1
    assert second["metrics_skipped"] == 1
    assert len(app_db.get_metrics("art_123", db_path)) == 1
