import json
import sys

from scripts import auto_fill_characters
from storage import app_db


def test_auto_fill_characters_script_applies_map(monkeypatch, tmp_path, capsys):
    db_path = str(tmp_path / "app.db")
    map_path = tmp_path / "character_map.csv"
    map_path.write_text("tag,character\nmiku,初音ミク\n", encoding="utf-8")
    artwork_id = app_db.create_artwork(
        tweet_id="1",
        url="https://x.com/example/status/1",
        title="Artwork",
        posted_at="2026-09-01T12:00:00+00:00",
        tags=["#Miku"],
        db_path=db_path,
    )

    monkeypatch.setattr(
        sys,
        "argv",
        ["auto_fill_characters.py", "--db", db_path, "--map", str(map_path)],
    )
    auto_fill_characters.main()

    output = json.loads(capsys.readouterr().out)
    assert output["scanned"] == 1
    assert output["filled"] == 1
    assert app_db.get_artwork(artwork_id, db_path)["characters"] == ["初音ミク"]
