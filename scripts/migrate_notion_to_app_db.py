"""Migrate Notion artworks and metric snapshots into app.db.

Usage:
    PYTHONPATH=. python scripts/migrate_notion_to_app_db.py
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from notion_client_wrapper import get_client
from processing import scheduler
from storage import app_db

logger = logging.getLogger("notion-migration")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def _text(prop: dict[str, Any], kind: str = "title") -> str:
    parts = prop.get(kind, [])
    return "".join(item.get("plain_text", item.get("text", {}).get("content", "")) for item in parts)


def _value(properties: dict[str, Any], name: str, kind: str, default: Any = None) -> Any:
    prop = properties.get(name, {})
    if kind in ("title", "rich_text"):
        return _text(prop, kind) or default
    value = prop.get(kind)
    if kind == "number":
        return value if value is not None else default
    if kind == "url":
        return value or default
    if kind == "date":
        return value.get("start") if value else default
    if kind == "select":
        return value.get("name") if value else default
    if kind == "multi_select":
        return [item.get("name") for item in (value or []) if item.get("name")]
    return default


def _image_urls(properties: dict[str, Any]) -> list[str]:
    files = properties.get(config.AW_PROP_IMAGE, {}).get("files", [])
    urls: list[str] = []
    for item in files:
        source = item.get("external", {}).get("url") or item.get("file", {}).get("url")
        if source:
            urls.append(source)
    return urls


def _tweet_id(url: str) -> str:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else url.rstrip("/").split("/")[-1]


def _pages(data_source_id: str) -> list[dict[str, Any]]:
    client = get_client()
    results: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        body: dict[str, Any] = {"page_size": 100}
        if cursor:
            body["start_cursor"] = cursor
        response = client.request(
            path=f"data_sources/{data_source_id}/query",
            method="POST",
            body=body,
        )
        results.extend(response.get("results", []))
        if not response.get("has_more"):
            return results
        cursor = response.get("next_cursor")
        if not cursor:
            return results


def _parse_iso(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def migrate() -> dict[str, int]:
    app_db.init_db()
    counts = {"artworks_fetched": 0, "artworks_inserted": 0, "artworks_skipped": 0, "metrics_fetched": 0, "metrics_inserted": 0, "metrics_skipped": 0, "errors": 0}
    page_to_artwork: dict[str, str] = {}

    artwork_pages = _pages(config.ARTWORKS_DB_ID)
    counts["artworks_fetched"] = len(artwork_pages)
    for page in artwork_pages:
        try:
            properties = page.get("properties", {})
            url = _value(properties, config.AW_PROP_URL, "url")
            posted_at = _value(properties, config.AW_PROP_POSTED_AT, "date")
            if not url or not posted_at:
                raise ValueError("URL または投稿日時がありません")
            status = _value(properties, config.AW_PROP_STATUS, "select", "TRACKING") or "TRACKING"
            if status not in config.STAGE_MAP and status != "COMPLETED":
                status = "TRACKING"
            tweet_id = _tweet_id(url)
            existing = app_db.find_artwork_by_tweet_id(tweet_id)
            artwork_id = app_db.upsert_artwork(
                tweet_id=tweet_id,
                url=url,
                title=_value(properties, config.AW_PROP_TITLE, "title", "Untitled"),
                posted_at=_parse_iso(posted_at),
                status=status,
                next_schedule=_value(properties, config.AW_PROP_NEXT_SCHEDULE, "date"),
                new_fans_count=_value(properties, config.AW_PROP_NEW_FANS_COUNT, "number", 0) or 0,
                image_urls=_image_urls(properties),
                tags=_value(properties, config.AW_PROP_TAGS, "multi_select", []),
            )
            page_to_artwork[page["id"]] = artwork_id
            counts["artworks_skipped" if existing else "artworks_inserted"] += 1
        except Exception as exc:
            counts["errors"] += 1
            logger.exception("作品ページ %s をスキップ: %s", page.get("id"), exc)

    metric_pages = _pages(config.METRICS_DB_ID)
    counts["metrics_fetched"] = len(metric_pages)
    for page in metric_pages:
        try:
            properties = page.get("properties", {})
            relation = properties.get(config.MS_PROP_PARENT_REL, {}).get("relation", [])
            parent_id = relation[0].get("id") if relation else None
            artwork_id = page_to_artwork.get(parent_id or "")
            if not artwork_id:
                raise ValueError(f"親作品が移行対象にありません: {parent_id}")
            stage = _value(properties, config.MS_PROP_ELAPSED, "select") or "5m"
            elapsed = config.STAGE_MAP.get(stage, {}).get("offset_sec")
            if elapsed is None:
                raise ValueError(f"不明なステージ: {stage}")
            measured_at = _value(properties, config.MS_PROP_MEASURED_AT, "date")
            if not measured_at:
                raise ValueError("計測日時がありません")
            existing_metric = app_db.metric_exists(artwork_id, stage)
            app_db.add_metric_snapshot(
                artwork_id,
                stage=stage,
                elapsed_seconds=elapsed,
                measured_at=_parse_iso(measured_at),
                impressions=_value(properties, config.MS_PROP_IMPRESSIONS, "number", 0) or 0,
                likes=_value(properties, config.MS_PROP_LIKES, "number", 0) or 0,
                retweets=_value(properties, config.MS_PROP_RETWEETS, "number", 0) or 0,
                followers=_value(properties, config.MS_PROP_FOLLOWERS, "number"),
                new_fans_count=_value(properties, config.MS_PROP_NEW_FANS, "number", 0) or 0,
            )
            counts["metrics_skipped" if existing_metric else "metrics_inserted"] += 1
        except Exception as exc:
            counts["errors"] += 1
            logger.exception("メトリクスページ %s をスキップ: %s", page.get("id"), exc)

    logger.info("移行完了: %s", counts)
    return counts


if __name__ == "__main__":
    migrate()
