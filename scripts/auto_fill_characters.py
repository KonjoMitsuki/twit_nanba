"""Fill characters from tags for all existing artworks in app.db.

Only artworks that have no character yet are updated. Manual selections,
including an intentionally cleared character, are never overwritten.

Usage:
    PYTHONPATH=. python scripts/auto_fill_characters.py --dry-run
    PYTHONPATH=. python scripts/auto_fill_characters.py --db ./app.db
    PYTHONPATH=. python scripts/auto_fill_characters.py --map ./data/character_map.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from processing.character_mapper import load_character_map, match_characters
from storage import app_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="Path to app.db (defaults to APP_DB_PATH)")
    parser.add_argument(
        "--map",
        dest="map_path",
        default=None,
        help="Path to the tag/character CSV (defaults to CHARACTER_MAP_PATH)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only report planned changes")
    args = parser.parse_args()

    map_path = Path(args.map_path or config.CHARACTER_MAP_PATH)
    mapping = load_character_map(map_path)
    if not mapping:
        parser.error(f"キャラクター対応表が空か存在しません: {map_path}")

    result = app_db.auto_fill_missing_characters(
        lambda tags: match_characters(tags, mapping),
        args.db,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
