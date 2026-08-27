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

from storage import fans_db

logger = logging.getLogger(__name__)


def compute_new_fans(
    current_likers: Set[str],
    known_users: Set[str],
) -> Set[str]:
    """差集合演算で新規反応者を算出する。

    Args:
        current_likers: 今回の投稿の反応者 @screen_name 集合。
        known_users: SQLite内の既知ユーザー集合。

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
    reaction_at: datetime,
    tweet_id: str | None = None,
    db_path: str = "fans.db",
) -> int:
    """新規反応者をローカルSQLiteに一括登録する。

    Args:
        new_fans: 新規反応者の @screen_name 集合。
        reaction_at: 反応検知日時。
        tweet_id: 初回反応ツイートID。
        db_path: SQLiteデータベースのパス。

    Returns:
        int: SQLiteに実際に追加されたユーザー数。
    """
    inserted_count = fans_db.register_new_fans(
        new_fans=new_fans,
        first_seen_at=reaction_at,
        tweet_id=tweet_id,
        db_path=db_path,
    )
    logger.info("SQLiteに新規ユーザーを登録: %d 名", inserted_count)
    return inserted_count
