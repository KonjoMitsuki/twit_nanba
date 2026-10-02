"""Resolve artwork characters from their stored tags."""

from __future__ import annotations

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize_tag(tag: str) -> str:
    return tag.strip().lstrip("#").strip().casefold()


def load_character_map(path: str | Path) -> dict[str, str]:
    mapping: dict[str, str] = {}
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as file:
            for row_number, row in enumerate(csv.DictReader(file), 2):
                tag = normalize_tag(row.get("tag", ""))
                character = (row.get("character") or "").strip()
                if not tag or not character:
                    logger.warning("対応表の行をスキップしました: %s:%d", path, row_number)
                    continue
                mapping.setdefault(tag, character)
    except FileNotFoundError:
        logger.info("キャラクター対応表が見つかりません: %s", path)
    return mapping


def character_for_tags(
    tags: list[str],
    path: str | Path,
) -> str | None:
    mapping = load_character_map(path)
    for tag in tags:
        character = mapping.get(normalize_tag(tag))
        if character:
            return character
    return None