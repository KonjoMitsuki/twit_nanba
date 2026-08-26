"""
notion_client_wrapper/users.py — 反応者マスターDB (User Master) CRUD
"""

from datetime import datetime
from typing import Any

import config
from notion_client_wrapper import get_client


def get_all_known_users() -> set[str]:
    """反応者マスターDB 内の全ユーザーID（@screen_name）を集合として返す。"""
    client = get_client()
    known: set[str] = set()
    has_more = True
    start_cursor: str | None = None

    while has_more:
        body: dict[str, Any] = {}
        if start_cursor:
            body["start_cursor"] = start_cursor

        response = client.request(
            path=f"data_sources/{config.USERS_DB_ID}/query",
            method="POST",
            body=body,
        )
        for page in response.get("results", []):
            title_parts = page["properties"][config.UM_PROP_TITLE].get("title", [])
            if title_parts:
                screen_name = title_parts[0]["plain_text"]
                known.add(screen_name)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return known


def find_user_page(screen_name: str) -> str | None:
    """screen_name で反応者マスターDBを検索し、該当ページ ID を返す。"""
    client = get_client()
    body = {
        "filter": {
            "property": config.UM_PROP_TITLE,
            "title": {"equals": screen_name},
        },
        "page_size": 1,
    }

    response = client.request(
        path=f"data_sources/{config.USERS_DB_ID}/query",
        method="POST",
        body=body,
    )

    results = response.get("results", [])
    if results:
        return results[0]["id"]
    return None


def create_user(screen_name: str, first_reaction_at: datetime, first_artwork_page_id: str) -> str:
    """新規ユーザーを反応者マスターDBに登録する。"""
    client = get_client()
    page = client.request(
        path="pages",
        method="POST",
        body={
            "parent": {"data_source_id": config.USERS_DB_ID},
            "properties": {
            config.UM_PROP_TITLE: {"title": [{"text": {"content": screen_name}}]},
            config.UM_PROP_FIRST_REACTION_AT: {"date": {"start": first_reaction_at.isoformat()}},
            config.UM_PROP_FIRST_ARTWORK_REL: {"relation": [{"id": first_artwork_page_id}]},
            },
        },
    )
    return page["id"]


def get_or_create_user(screen_name: str, first_reaction_at: datetime, first_artwork_page_id: str) -> tuple[str, bool]:
    """ユーザーが存在すれば取得、なければ新規作成する。"""
    existing_id = find_user_page(screen_name)
    if existing_id is not None:
        return existing_id, False

    new_id = create_user(screen_name, first_reaction_at, first_artwork_page_id)
    return new_id, True
