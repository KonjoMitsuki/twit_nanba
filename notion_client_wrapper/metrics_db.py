"""
notion_client_wrapper/metrics_db.py — 時系列メトリクスDB (Metrics Snapshots) CRUD

各計測時点のエンゲージメントスナップショットを
時系列メトリクスDBに保存する操作を提供します。
"""

from datetime import datetime, timezone, timedelta

import config
from notion_client_wrapper import get_client


def create_snapshot(
    artwork_page_id: str,
    stage: str,
    impressions: int,
    likes: int,
    retweets: int,
    new_fans_count: int = 0,
    followers: int = 0,
) -> str:
    """時系列メトリクスDBにスナップショット行を挿入する。

    Args:
        artwork_page_id: 親作品ページの ID（リレーション用）。
        stage: 経過時間ステージ名（例: "1h", "6h"）。
        impressions: インプレッション数。
        likes: いいね数。
        retweets: リツイート数。
        new_fans_count: このステージで検知された新規反応者数。
        followers: 投稿者のフォロワー数。

    Returns:
        str: 作成されたスナップショットページの ID。
    """
    client = get_client()
    now = datetime.now(timezone.utc)

    # ログ名: "1h (08/18 22:00)" 形式
    # ローカル時間で表示するため JST に変換（+9h）
    jst = timezone(timedelta(hours=9))
    now_jst = now.astimezone(jst)
    log_name = f"{stage} ({now_jst.strftime('%m/%d %H:%M')})"

    page = client.request(
        path="pages",
        method="POST",
        body={
            "parent": {"data_source_id": config.METRICS_DB_ID},
            "properties": {
            config.MS_PROP_TITLE: {
                "title": [{"text": {"content": log_name}}],
            },
            config.MS_PROP_PARENT_REL: {
                "relation": [{"id": artwork_page_id}],
            },
            config.MS_PROP_MEASURED_AT: {
                "date": {"start": now.isoformat()},
            },
            config.MS_PROP_ELAPSED: {
                "select": {"name": stage},
            },
            config.MS_PROP_IMPRESSIONS: {
                "number": impressions,
            },
            config.MS_PROP_LIKES: {
                "number": likes,
            },
            config.MS_PROP_RETWEETS: {
                "number": retweets,
            },
            config.MS_PROP_NEW_FANS: {
                "number": new_fans_count,
            },
            config.MS_PROP_FOLLOWERS: {
                "number": followers,
            },
            },
        },
    )
    return page["id"]
