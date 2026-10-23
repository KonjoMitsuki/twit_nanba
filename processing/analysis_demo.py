"""Synthetic demo data. No application DB, Notion or X access."""

import math
from datetime import datetime, timedelta

import config
from storage.app_db import JST

CHARACTERS = ["初音ミク", "巡音ルカ", "鏡音リン", "鏡音レン"]


def demo_rows(source, stage="24h", overrides=None):
    now = datetime.now(JST).replace(hour=12, minute=0, second=0, microsecond=0)
    rows = []
    if source == "followers":
        for day in range(65):
            time = now - timedelta(days=64 - day)
            rows.append(
                {
                    "id": f"demo_account_{day}",
                    "row_id": f"demo_account_{day}",
                    "date": time.date().isoformat(),
                    "measured_at": time.isoformat(),
                    "followers": 4200 + day * 15 + round(math.sin(day / 4) * 20),
                }
            )
        return rows
    for i in range(32):
        posted = now - timedelta(days=62 - i * 2)
        identity = f"demo_art_{i}"
        characters = [CHARACTERS[i % 4]] + (
            [CHARACTERS[(i + 1) % 4]] if i % 5 == 0 else []
        )
        characters = (overrides or {}).get(identity, characters)
        base = 120 + (i * 83) % 600 + (i % 4) * 80
        stages = (
            config.SCHEDULE_STAGES
            if source == "snapshots"
            else [config.STAGE_MAP[stage]]
        )
        for definition in stages:
            seconds = definition["offset_sec"]
            missing = source == "artworks" and i % 11 == 0
            growth = 1 - math.exp(-seconds / 20000)
            likes = round(base * growth * (1 + i / 90))
            measured = posted + timedelta(seconds=seconds)
            rows.append(
                {
                    "id": identity
                    if source == "artworks"
                    else f"{identity}_{definition['name']}",
                    "row_id": identity
                    if source == "artworks"
                    else f"{identity}_{definition['name']}",
                    "artwork_id": identity,
                    "snapshot_id": None
                    if missing
                    else f"{identity}_{definition['name']}",
                    "title": f"{characters[0] if characters else '無題'} / Study {i + 1:02}",
                    "url": "",
                    "image_urls": ["/demo-artwork.svg"] * (1 + i % 4) if i % 11 else [],
                    "date": posted.date().isoformat(),
                    "posted_at": posted.isoformat(),
                    "measured_at": None if missing else measured.isoformat(),
                    "status": "COMPLETED",
                    "stage": None if missing else definition["name"],
                    "characters": characters,
                    "character": " + ".join(characters) or "未設定",
                    "tags": ["イラスト", *characters],
                    "elapsed_seconds": None if missing else seconds,
                    "elapsed_hours": None if missing else seconds / 3600,
                    "likes": None if missing else likes,
                    "retweets": None if missing else round(likes * 0.11),
                    "impressions": None if missing else likes * (12 + i % 6),
                    "followers": None if missing else 4200 + i * 30,
                    "new_fans_count": None if missing else round(likes * 0.04),
                }
            )
    return rows
