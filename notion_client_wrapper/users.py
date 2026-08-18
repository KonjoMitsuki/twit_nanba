"""
notion_client_wrapper/users.py — 反応者マスターDB (User Master) CRUD

反応者ユーザーの検索・登録・全件取得を提供します。
ページネーション対応で 100 件超のデータベースにも対応。
"""

from datetime import datetime, timezone
from typing import Any

import config
from notion_client_wrapper import get_client


def get_all_known_users() -> set[str]:
    """反応者マスターDB 内の全ユーザーID（@screen_name）を集合として返す。

    ページネーションに対応し、全件を取得します。

    Returns:
        set[str]: 既知の全ユーザー @screen_name の集合。
    """
    client = get_client()
    known: set[str] = set()
    has_more = True
    start_cursor: str | None = None

    while has_more:
        response = client.databases.query(
            database_id=config.USERS_DB_ID,
            start_cursor=start_cursor,
        )
        for page in response["results"]:
            title_parts = page["properties"][config.UM_PROP_TITLE].get(
                "title", []
            )
            if title_parts:
                screen_name = title_parts[0]["plain_text"]
                known.add(screen_name)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return known


def find_user_page(screen_name: str) -> str | None:
    """screen_name で反応者マスターDBを検索し、該当ページ ID を返す。

    Args:
        screen_name: 検索対象の @screen_name。

    Returns:
        str | None: ページ ID。見つからなければ None。
    """
    client = get_client()
    response = client.databases.query(
        database_id=config.USERS_DB_ID,
        filter={
            "property": config.UM_PROP_TITLE,
            "title": {
                "equals": screen_name,
            },
        },
        page_size=1,
    )

    results = response.get("results", [])
    if results:
        return results[0]["id"]
    return None


def create_user(
    screen_name: str,
    first_reaction_at: datetime,
    first_artwork_page_id: str,
) -> str:
    """新規ユーザーを反応者マスターDBに登録する。

    Args:
        screen_name: @screen_name。
        first_reaction_at: 初回反応日時。
        first_artwork_page_id: 初回反応作品の Notion ページ ID。

    Returns:
        str: 作成されたユーザーページの ID。
    """
    client = get_client()
    page = client.pages.create(
        parent={"database_id": config.USERS_DB_ID},
        properties={
            config.UM_PROP_TITLE: {
                "title": [{"text": {"content": screen_name}}],
            },
            config.UM_PROP_FIRST_REACTION_AT: {
                "date": {"start": first_reaction_at.isoformat()},
            },
            config.UM_PROP_FIRST_ARTWORK_REL: {
                "relation": [{"id": first_artwork_page_id}],
            },
        },
    )
    return page["id"]


def get_or_create_user(
    screen_name: str,
    first_reaction_at: datetime,
    first_artwork_page_id: str,
) -> tuple[str, bool]:
    """ユーザーが存在すれば取得、なければ新規作成する。

    Args:
        screen_name: @screen_name。
        first_reaction_at: 初回反応日時。
        first_artwork_page_id: 初回反応作品のページ ID。

    Returns:
        tuple[str, bool]: (ページ ID, 新規作成されたか)。
    """
    existing_id = find_user_page(screen_name)
    if existing_id is not None:
        return existing_id, False

    new_id = create_user(screen_name, first_reaction_at, first_artwork_page_id)
    return new_id, True
