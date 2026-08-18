"""
processing/scheduler.py — 状態遷移エンジン

計測スケジュールに基づき、現在のステージから次のステージへの遷移と
次回予定日時の算出を行います。

状態遷移: 5m → 15m → 30m → 1h → 2h → 3h → 6h → 12h → 24h → 48h → COMPLETED
"""

from datetime import datetime, timedelta
from typing import Optional

import config


def get_next_stage(current_stage: str) -> Optional[str]:
    """現在のステージから次のステージ名を返す。

    Args:
        current_stage: 現在のステータス名（例: "5m", "1h"）。

    Returns:
        str | None: 次のステージ名。"48h" の場合は None（COMPLETED へ遷移）。

    Raises:
        ValueError: 不明なステージ名が指定された場合。
    """
    if current_stage not in config.STAGE_MAP:
        raise ValueError(f"不明なステージ名: {current_stage}")

    try:
        current_index = config.STAGE_NAMES.index(current_stage)
    except ValueError:
        raise ValueError(f"不明なステージ名: {current_stage}")

    next_index = current_index + 1
    if next_index >= len(config.STAGE_NAMES):
        return None  # COMPLETED

    return config.STAGE_NAMES[next_index]


def calculate_next_schedule(
    posted_at: datetime,
    next_stage: str,
) -> datetime:
    """投稿日時と次ステージ名から、次回予定日時を算出する。

    次回予定日時 = 投稿日時 + 次ステージのオフセット秒数

    Args:
        posted_at: ツイートの投稿日時。
        next_stage: 次のステージ名（例: "15m", "1h"）。

    Returns:
        datetime: 次回予定日時。

    Raises:
        ValueError: 不明なステージ名が指定された場合。
    """
    if next_stage not in config.STAGE_MAP:
        raise ValueError(f"不明なステージ名: {next_stage}")

    offset_sec = config.STAGE_MAP[next_stage]["offset_sec"]
    return posted_at + timedelta(seconds=offset_sec)


def is_fan_collection_stage(stage: str) -> bool:
    """指定ステージがユーザー照合（いいねモーダル取得）を行うステージか判定する。

    Args:
        stage: ステージ名。

    Returns:
        bool: ユーザー照合を行うなら True。
    """
    if stage not in config.STAGE_MAP:
        raise ValueError(f"不明なステージ名: {stage}")

    return config.STAGE_MAP[stage]["with_fans"]


def get_stage_display_name(stage: str) -> str:
    """ステージ名の表示用文字列を返す。

    Args:
        stage: ステージ名。

    Returns:
        str: 表示用文字列（例: "1h (+1時間)"）。
    """
    offset = config.STAGE_MAP.get(stage, {}).get("offset_sec", 0)

    if offset < 3600:
        display = f"+{offset // 60}分"
    else:
        display = f"+{offset // 3600}時間"

    return f"{stage} ({display})"
