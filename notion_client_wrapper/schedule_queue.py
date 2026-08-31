"""
notion_client_wrapper/schedule_queue.py — 予約投稿DB (Schedule Queue) CRUD

Notion 上の予約投稿DBから投稿予定レコードを取得し、
投稿結果に応じてステータスを更新する操作を提供します。
"""

from datetime import datetime, timezone
from typing import Any

import config
from notion_client_wrapper import get_client


def get_due_scheduled_posts() -> list[dict[str, Any]]:
    """「ステータス == SCHEDULED」かつ「投稿予約日時 <= 現在時刻」のレコード一覧を取得する。

    Returns:
        list[dict]: 投稿対象のNotionページオブジェクトのリスト。
    """
    if not config.SCHEDULE_QUEUE_DB_ID:
        return []

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
                        "property": config.SQ_PROP_STATUS,
                        "select": {"equals": config.STATUS_SQ_SCHEDULED},
                    },
                    {
                        "property": config.SQ_PROP_SCHEDULED_AT,
                        "date": {"on_or_before": now_iso},
                    },
                ]
            }
        }
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = client.request(
            path=f"data_sources/{config.SCHEDULE_QUEUE_DB_ID}/query",
            method="POST",
            body=body,
        )
        results.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return results


def extract_scheduled_post_info(page: dict[str, Any]) -> dict[str, Any]:
    """Notion ページオブジェクトから予約投稿情報を抽出する。

    Args:
        page: Notion API のページオブジェクト。

    Returns:
        dict: 以下のキーを含む辞書:
            - page_id: ページID
            - title: タイトル（作品名）
            - text: 本文（ツイート本文）
            - image_urls: 添付画像URLリスト
            - scheduled_at: 投稿予約日時（ISO文字列）
    """
    props = page["properties"]

    # タイトル
    title_parts = props[config.SQ_PROP_TITLE].get("title", [])
    title = title_parts[0]["plain_text"] if title_parts else ""

    # 本文（Rich Text — plain_text を連結して改行を維持）
    rich_text_parts = props[config.SQ_PROP_TEXT].get("rich_text", [])
    text = "".join(part["plain_text"] for part in rich_text_parts)

    # 添付画像
    files_prop = props.get(config.SQ_PROP_ATTACHMENTS, {})
    files_list = files_prop.get("files", [])
    image_urls: list[str] = []
    for f in files_list:
        # Notion のファイルは "file" (内部) または "external" タイプ
        if f.get("type") == "file":
            url = f.get("file", {}).get("url", "")
        elif f.get("type") == "external":
            url = f.get("external", {}).get("url", "")
        else:
            url = ""
        if url:
            image_urls.append(url)

    # 投稿予約日時
    date_prop = props.get(config.SQ_PROP_SCHEDULED_AT, {}).get("date")
    scheduled_at = date_prop["start"] if date_prop else None

    return {
        "page_id": page["id"],
        "title": title,
        "text": text,
        "image_urls": image_urls,
        "scheduled_at": scheduled_at,
    }


def mark_as_posted(page_id: str, tweet_url: str) -> None:
    """予約投稿レコードのステータスを POSTED に更新し、投稿後URLをセットする。

    Args:
        page_id: 対象ページの ID。
        tweet_url: 投稿成功後のツイート URL。
    """
    client = get_client()
    client.request(
        path=f"pages/{page_id}",
        method="PATCH",
        body={
            "properties": {
                config.SQ_PROP_STATUS: {
                    "select": {"name": config.STATUS_SQ_POSTED},
                },
                config.SQ_PROP_POSTED_URL: {
                    "url": tweet_url,
                },
            }
        },
    )


def mark_as_failed(page_id: str) -> None:
    """予約投稿レコードのステータスを FAILED に更新する。

    Args:
        page_id: 対象ページの ID。
    """
    client = get_client()
    client.request(
        path=f"pages/{page_id}",
        method="PATCH",
        body={
            "properties": {
                config.SQ_PROP_STATUS: {
                    "select": {"name": config.STATUS_SQ_FAILED},
                },
            }
        },
    )
