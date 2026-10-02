from fastapi.testclient import TestClient

import config
from api.main import app
from storage import app_db


def test_character_update_and_auto_fill(monkeypatch, tmp_path):
    db_path = str(tmp_path / "app.db")
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    mapping_path = tmp_path / "character_map.csv"
    mapping_path.write_text("tag,character\nmiku,初音ミク\n", encoding="utf-8")
    monkeypatch.setattr(config, "CHARACTER_MAP_PATH", str(mapping_path))

    artwork_id = app_db.create_artwork(
        tweet_id="api-test-1",
        url="https://x.com/example/status/api-test-1",
        title="API test",
        posted_at="2026-09-01T12:00:00+00:00",
        tags=["#miku"],
    )

    client = TestClient(app)
    response = client.post(f"/api/artworks/{artwork_id}/character/auto")
    assert response.status_code == 200
    assert response.json()["character"] == "初音ミク"

    response = client.patch(
        f"/api/artworks/{artwork_id}",
        json={"character": "巡音ルカ"},
    )
    assert response.status_code == 200
    assert response.json()["character"] == "巡音ルカ"

    response = client.patch(
        f"/api/artworks/{artwork_id}",
        json={"character": ""},
    )
    assert response.status_code == 200
    assert response.json()["character"] is None


def test_auto_fill_does_not_overwrite_manual_character(monkeypatch, tmp_path):
    db_path = str(tmp_path / "app.db")
    monkeypatch.setattr(app_db, "DB_PATH", db_path)
    mapping_path = tmp_path / "character_map.csv"
    mapping_path.write_text("tag,character\nmiku,初音ミク\n", encoding="utf-8")
    monkeypatch.setattr(config, "CHARACTER_MAP_PATH", str(mapping_path))

    artwork_id = app_db.create_artwork(
        tweet_id="api-test-2",
        url="https://x.com/example/status/api-test-2",
        title="API test",
        posted_at="2026-09-01T12:00:00+00:00",
        character="手動入力",
        tags=["miku"],
    )

    response = TestClient(app).post(f"/api/artworks/{artwork_id}/character/auto")
    assert response.status_code == 200
    assert response.json()["character"] == "手動入力"