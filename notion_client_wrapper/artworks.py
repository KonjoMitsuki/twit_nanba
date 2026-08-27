"""
notion_client_wrapper/artworks.py — 作品マスターDB (Art Works) CRUD
"""

from datetime import datetime, timezone
from typing import Any

import config
from notion_client_wrapper import get_client


def get_due_artworks() -> list[dict[str, Any]]:
    """「次回予定 <= 現在時刻」かつ「ステータス != COMPLETED」の作品一覧を取得する。"""
    client = get_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    results: list[dict[str, Any]] = []
    has_more = True
    start_cursor: str | None = None

    while has_more:
        body: dict[str, Any] = {
            "filter": {
                "and": [
                    {
                        "property": config.AW_PROP_NEXT_SCHEDULE,
                        "date": {"on_or_before": now_iso},
                    },
                    {
                        "property": config.AW_PROP_STATUS,
                        "select": {"does_not_equal": "COMPLETED"},
                    },
                ]
            }
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = client.request(
            path=f"data_sources/{config.ARTWORKS_DB_ID}/query",
            method="POST",
            body=body,
        )
        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return results


def find_by_tweet_url(url: str) -> dict[str, Any] | None:
    """ツイート URL で作品マスターDB を検索し、該当ページを返す。"""
    client = get_client()

    body = {
        "filter": {
            "property": config.AW_PROP_URL,
            "url": {"equals": url},
        },
        "page_size": 1,
    }

    response = client.request(
        path=f"data_sources/{config.ARTWORKS_DB_ID}/query",
        method="POST",
        body=body,
    )

    results = response.get("results", [])
    return results[0] if results else None


def create_artwork(
    url: str,
    title: str,
    posted_at: datetime,
    image_url: str = None,
) -> str:
    """新規作品をマスターDBに登録する。"""
    client = get_client()
    first_stage = config.SCHEDULE_STAGES[0]
    from processing.scheduler import calculate_next_schedule

    next_schedule = calculate_next_schedule(posted_at, first_stage["name"])

    properties: dict[str, Any] = {
        config.AW_PROP_TITLE: {"title": [{"text": {"content": title}}]},
        config.AW_PROP_URL: {"url": url},
        config.AW_PROP_POSTED_AT: {"date": {"start": posted_at.isoformat()}},
        config.AW_PROP_STATUS: {"select": {"name": first_stage["name"]}},
        config.AW_PROP_NEXT_SCHEDULE: {"date": {"start": next_schedule.isoformat()}},
        config.AW_PROP_NEW_FANS_COUNT: {"number": 0},
    }
    if image_url:
        properties[config.AW_PROP_IMAGE] = {
            "files": [
                {
                    "name": "サムネイル",
                    "type": "external",
                    "external": {"url": image_url},
                }
            ]
        }

    page = client.request(
        path="pages",
        method="POST",
        body={
            "parent": {"data_source_id": config.ARTWORKS_DB_ID},
            "properties": properties,
        },
    )
    return page["id"]


def create_artwork_auto(
    url: str,
    title: str,
    posted_at: datetime,
    initial_stage: str,
    image_url: str = None,
) -> str:
    """自動検知用の新規作品登録。"""
    if initial_stage not in config.STAGE_MAP:
        raise ValueError(f"不明なステージ名: {initial_stage}")

    client = get_client()
    from processing.scheduler import calculate_next_schedule

    next_schedule = calculate_next_schedule(posted_at, initial_stage)

    properties: dict[str, Any] = {
        config.AW_PROP_TITLE: {"title": [{"text": {"content": title}}]},
        config.AW_PROP_URL: {"url": url},
        config.AW_PROP_POSTED_AT: {"date": {"start": posted_at.isoformat()}},
        config.AW_PROP_STATUS: {"select": {"name": initial_stage}},
        config.AW_PROP_NEXT_SCHEDULE: {"date": {"start": next_schedule.isoformat()}},
        config.AW_PROP_NEW_FANS_COUNT: {"number": 0},
    }
    if image_url:
        properties[config.AW_PROP_IMAGE] = {
            "files": [
                {
                    "name": "サムネイル",
                    "type": "external",
                    "external": {"url": image_url},
                }
            ]
        }

    page = client.request(
        path="pages",
        method="POST",
        body={
            "parent": {"data_source_id": config.ARTWORKS_DB_ID},
            "properties": properties,
        },
    )
    return page["id"]


def update_status(page_id: str, new_status: str, next_schedule: datetime | None) -> None:
    """作品のステータスと次回予定を更新する。"""
    client = get_client()
    properties: dict[str, Any] = {
        config.AW_PROP_STATUS: {"select": {"name": new_status}},
    }
    if next_schedule is not None:
        properties[config.AW_PROP_NEXT_SCHEDULE] = {"date": {"start": next_schedule.isoformat()}}
    else:
        properties[config.AW_PROP_NEXT_SCHEDULE] = {"date": None}

    client.request(path=f"pages/{page_id}", method="PATCH", body={"properties": properties})


def update_new_fans_count(page_id: str, count: int) -> None:
    """「はじめて反応した人の数」を更新する。"""
    client = get_client()
    client.request(
        path=f"pages/{page_id}",
        method="PATCH",
        body={"properties": {config.AW_PROP_NEW_FANS_COUNT: {"number": count}}},
    )


def add_metrics_relation(page_id: str, metrics_page_id: str) -> None:
    """時系列ログリレーションにスナップショットを追加する。"""
    client = get_client()
    page = client.request(path=f"pages/{page_id}", method="GET")
    current_relations = page["properties"][config.AW_PROP_METRICS_REL].get("relation", [])
    current_relations.append({"id": metrics_page_id})

    client.request(
        path=f"pages/{page_id}",
        method="PATCH",
        body={"properties": {config.AW_PROP_METRICS_REL: {"relation": current_relations}}},
    )


def extract_artwork_info(page: dict[str, Any]) -> dict[str, Any]:
    """Notion ページオブジェクトから作品情報を抽出する。"""
    props = page["properties"]
    title_parts = props[config.AW_PROP_TITLE].get("title", [])
    title = title_parts[0]["plain_text"] if title_parts else ""
    url = props[config.AW_PROP_URL].get("url", "")

    posted_at_prop = props[config.AW_PROP_POSTED_AT].get("date")
    posted_at = posted_at_prop["start"] if posted_at_prop else None

    status_prop = props[config.AW_PROP_STATUS].get("select")
    status = status_prop["name"] if status_prop else None

    next_sched_prop = props[config.AW_PROP_NEXT_SCHEDULE].get("date")
    next_schedule = next_sched_prop["start"] if next_sched_prop else None

    new_fans_count = props[config.AW_PROP_NEW_FANS_COUNT].get("number", 0) or 0

    return {
        "page_id": page["id"],
        "title": title,
        "url": url,
        "posted_at": posted_at,
        "status": status,
        "next_schedule": next_schedule,
        "new_fans_count": new_fans_count,
    }
