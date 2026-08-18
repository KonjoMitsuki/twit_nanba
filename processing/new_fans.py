"""
processing/new_fans.py — 新規反応者判定アルゴリズム

過去の全反応者集合 U_past と今回の反応者集合 U_current の差集合を求め、
新規反応者を判定します。

    U_new = U_current \\ U_past
    N_new = |U_new|
"""

import logging
from datetime import datetime
from typing import Set

from notion_client_wrapper import users as users_db
from notion_client_wrapper import artworks as artworks_db

logger = logging.getLogger(__name__)


def compute_new_fans(
    current_likers: Set[str],
    known_users: Set[str],
) -> Set[str]:
    """差集合演算で新規反応者を算出する。

    Args:
        current_likers: 今回の投稿の反応者 @screen_name 集合。
        known_users: 反応者マスターDB 内の既知ユーザー集合。

    Returns:
        set[str]: 新規反応者の @screen_name 集合。
    """
    new_fans = current_likers - known_users
    logger.info(
        "差集合演算: current=%d, known=%d → new=%d",
        len(current_likers),
        len(known_users),
        len(new_fans),
    )
    return new_fans


def register_new_fans(
    new_fans: Set[str],
    artwork_page_id: str,
    reaction_at: datetime,
) -> list[str]:
    """新規反応者を反応者マスターDBに登録し、作品リレーションを更新する。

    Args:
        new_fans: 新規反応者の @screen_name 集合。
        artwork_page_id: 初回反応作品の Notion ページ ID。
        reaction_at: 反応検知日時。

    Returns:
        list[str]: 登録・取得されたユーザーページ ID のリスト。
    """
    user_page_ids: list[str] = []

    for screen_name in new_fans:
        try:
            page_id, is_new = users_db.get_or_create_user(
                screen_name=screen_name,
                first_reaction_at=reaction_at,
                first_artwork_page_id=artwork_page_id,
            )
            user_page_ids.append(page_id)

            if is_new:
                logger.info("新規ユーザー登録: %s", screen_name)
            else:
                logger.debug("既存ユーザー: %s", screen_name)

        except Exception as e:
            logger.warning(
                "ユーザー登録失敗 (%s): %s", screen_name, e
            )

    # 作品の反応ユーザーリレーションに追加
    if user_page_ids:
        try:
            artworks_db.add_user_relations(artwork_page_id, user_page_ids)
            logger.info(
                "作品リレーション更新: %d 名追加", len(user_page_ids)
            )
        except Exception as e:
            logger.warning("作品リレーション更新失敗: %s", e)

    return user_page_ids
