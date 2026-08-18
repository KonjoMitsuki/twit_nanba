"""
notion_client_wrapper/artworks.py — 作品マスターDB (Art Works) CRUD

Notion の作品マスターDBに対して、フィルタクエリ・作成・更新操作を提供します。
"""

from datetime import datetime, timezone
from typing import Any

import config
from notion_client_wrapper import get_client


def get_due_artworks() -> list[dict[str, Any]]:
    """「次回予定 <= 現在時刻」かつ「ステータス != COMPLETED」の作品一覧を取得する。

    Returns:
        list[dict]: 各作品の Notion ページオブジェクト（properties 含む）。
    """
    client = get_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    results: list[dict[str, Any]] = []
    has_more = True
    start_cursor: str | None = None

    while has_more:
        response = client.databases.query(
            database_id=config.ARTWORKS_DB_ID,
            filter={
                "and": [
                    {
                        "property": config.AW_PROP_NEXT_SCHEDULE,
                        "date": {
                            "on_or_before": now_iso,
                        },
                    },
                    {
                        "property": config.AW_PROP_STATUS,
                        "select": {
                            "does_not_equal": "COMPLETED",
                        },
                    },
                ]
            },
            start_cursor=start_cursor,
        )
        results.extend(response["results"])
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return results


def create_artwork(
    url: str,
    title: str,
    posted_at: datetime,
) -> str:
    """新規作品をマスターDBに登録する。

    Args:
        url: ツイートの直リンク URL。
        title: 作品名（ツイート本文の先頭部分など）。
        posted_at: 投稿日時。

    Returns:
        str: 作成されたページの ID。
    """
    client = get_client()

    # 初回ステータスは "5m"、次回予定は posted_at + 5分
    first_stage = config.SCHEDULE_STAGES[0]
    from processing.scheduler import calculate_next_schedule

    next_schedule = calculate_next_schedule(posted_at, first_stage["name"])

    page = client.pages.create(
        parent={"database_id": config.ARTWORKS_DB_ID},
        properties={
            config.AW_PROP_TITLE: {
                "title": [{"text": {"content": title}}],
            },
            config.AW_PROP_URL: {
                "url": url,
            },
            config.AW_PROP_POSTED_AT: {
                "date": {"start": posted_at.isoformat()},
            },
            config.AW_PROP_STATUS: {
                "select": {"name": first_stage["name"]},
            },
            config.AW_PROP_NEXT_SCHEDULE: {
                "date": {"start": next_schedule.isoformat()},
            },
            config.AW_PROP_NEW_FANS_COUNT: {
                "number": 0,
            },
        },
    )
    return page["id"]


def update_status(
    page_id: str,
    new_status: str,
    next_schedule: datetime | None,
) -> None:
    """作品のステータスと次回予定を更新する。

    Args:
        page_id: 対象ページの ID。
        new_status: 新しいステータス名（例: "15m", "COMPLETED"）。
        next_schedule: 次回予定日時。COMPLETED 時は None。
    """
    client = get_client()

    properties: dict[str, Any] = {
        config.AW_PROP_STATUS: {
            "select": {"name": new_status},
        },
    }

    if next_schedule is not None:
        properties[config.AW_PROP_NEXT_SCHEDULE] = {
            "date": {"start": next_schedule.isoformat()},
        }
    else:
        # COMPLETED 時は次回予定をクリア
        properties[config.AW_PROP_NEXT_SCHEDULE] = {
            "date": None,
        }

    client.pages.update(page_id=page_id, properties=properties)


def update_new_fans_count(page_id: str, count: int) -> None:
    """「はじめて反応した人の数」を更新する。

    Args:
        page_id: 対象ページの ID。
        count: 累計の新規反応者数。
    """
    client = get_client()
    client.pages.update(
        page_id=page_id,
        properties={
            config.AW_PROP_NEW_FANS_COUNT: {
                "number": count,
            },
        },
    )


def add_user_relations(page_id: str, user_page_ids: list[str]) -> None:
    """反応ユーザーリレーションに新規ユーザーを追加する。

    既存のリレーションを保持しつつ、新しいユーザーを追加します。

    Args:
        page_id: 対象作品ページの ID。
        user_page_ids: 追加するユーザーページ ID のリスト。
    """
    if not user_page_ids:
        return

    client = get_client()

    # 現在のリレーション一覧を取得
    page = client.pages.retrieve(page_id=page_id)
    current_relations = page["properties"][config.AW_PROP_USERS_REL].get(
        "relation", []
    )

    # 既存 ID のセット
    existing_ids = {r["id"] for r in current_relations}

    # 重複を避けて追加
    for uid in user_page_ids:
        if uid not in existing_ids:
            current_relations.append({"id": uid})

    client.pages.update(
        page_id=page_id,
        properties={
            config.AW_PROP_USERS_REL: {
                "relation": current_relations,
            },
        },
    )


def add_metrics_relation(page_id: str, metrics_page_id: str) -> None:
    """時系列ログリレーションにスナップショットを追加する。

    Args:
        page_id: 対象作品ページの ID。
        metrics_page_id: 追加するメトリクスページの ID。
    """
    client = get_client()

    # 現在のリレーション一覧を取得
    page = client.pages.retrieve(page_id=page_id)
    current_relations = page["properties"][config.AW_PROP_METRICS_REL].get(
        "relation", []
    )

    current_relations.append({"id": metrics_page_id})

    client.pages.update(
        page_id=page_id,
        properties={
            config.AW_PROP_METRICS_REL: {
                "relation": current_relations,
            },
        },
    )


# ─── ヘルパー関数 ─────────────────────────────────────────────

def extract_artwork_info(page: dict[str, Any]) -> dict[str, Any]:
    """Notion ページオブジェクトから作品情報を辞書として抽出する。

    Args:
        page: Notion API から返されたページオブジェクト。

    Returns:
        dict: 以下のキーを含む辞書:
            - page_id: ページ ID
            - title: 作品名
            - url: ツイート URL
            - posted_at: 投稿日時 (ISO 8601 文字列)
            - status: 現在のステータス
            - next_schedule: 次回予定日時 (ISO 8601 文字列 or None)
            - new_fans_count: 累計新規反応者数
    """
    props = page["properties"]

    # タイトル
    title_parts = props[config.AW_PROP_TITLE].get("title", [])
    title = title_parts[0]["plain_text"] if title_parts else ""

    # URL
    url = props[config.AW_PROP_URL].get("url", "")

    # 投稿日時
    posted_at_prop = props[config.AW_PROP_POSTED_AT].get("date")
    posted_at = posted_at_prop["start"] if posted_at_prop else None

    # ステータス
    status_prop = props[config.AW_PROP_STATUS].get("select")
    status = status_prop["name"] if status_prop else None

    # 次回予定
    next_sched_prop = props[config.AW_PROP_NEXT_SCHEDULE].get("date")
    next_schedule = next_sched_prop["start"] if next_sched_prop else None

    # はじめて反応した人の数
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
