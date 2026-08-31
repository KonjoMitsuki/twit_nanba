"""
config.py — システム全体の設定管理

.env から環境変数を読み込み、計測スケジュール・状態遷移テーブル・
アンチスクレイピングパラメータなどの定数を一元管理します。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env ファイルの読み込み
load_dotenv(Path(__file__).parent / ".env")

# =============================================================================
# Notion API 設定
# =============================================================================
NOTION_TOKEN: str = os.getenv("NOTION_TOKEN", "")
ARTWORKS_DB_ID: str = os.getenv("ARTWORKS_DB_ID", "")
METRICS_DB_ID: str = os.getenv("METRICS_DB_ID", "")
SCHEDULE_QUEUE_DB_ID: str = os.getenv("SCHEDULE_QUEUE_DB_ID", "")
FANS_DB_PATH: str = os.getenv(
    "FANS_DB_PATH",
    str(Path(__file__).parent / "fans.db"),
)

# =============================================================================
# Playwright 認証設定
# =============================================================================
X_AUTH_STATE_PATH: str = os.getenv(
    "X_AUTH_STATE_PATH",
    str(Path(__file__).parent / "auth_state.json"),
)

# =============================================================================
# 計測スケジュール定義
# =============================================================================
# 各ステージの定義:
#   name       : ステータス名（Notion セレクトプロパティ値）
#   offset_sec : 投稿日時からの経過秒数
#   with_fans  : True ならユーザー照合（いいねモーダル取得）を実施
SCHEDULE_STAGES: list[dict] = [
    {"name": "5m",  "offset_sec": 300,  "with_fans": False},
    {"name": "15m", "offset_sec": 900,  "with_fans": False},
    {"name": "30m", "offset_sec": 1800, "with_fans": False},
    {"name": "1h",  "offset_sec": 3600, "with_fans": True},
    *[
        {
            "name": f"{hours}h",
            "offset_sec": hours * 3600,
            "with_fans": False,
        }
        for hours in range(2, 48)
    ],
    {"name": "48h", "offset_sec": 48 * 3600, "with_fans": True},
]

# ステージ名のリスト（状態遷移用）
STAGE_NAMES: list[str] = [s["name"] for s in SCHEDULE_STAGES]

# ステージ名 → 定義辞書のマッピング
STAGE_MAP: dict[str, dict] = {s["name"]: s for s in SCHEDULE_STAGES}

# =============================================================================
# アンチスクレイピング パラメータ
# =============================================================================
# ランダムウェイト範囲（秒）
WAIT_MIN_SEC: float = 2.0
WAIT_MAX_SEC: float = 5.0

# いいねモーダル スクロール制限
MAX_LIKERS: int = 200          # 最大取得ユーザー数
MAX_SCROLL_COUNT: int = 5      # 最大スクロール回数

# GraphQL レスポンス待機タイムアウト（秒）
GRAPHQL_TIMEOUT_SEC: float = 15.0

# 対象ゼロ時の無負荷終了待機（秒）
NO_TARGET_WAIT_SEC: float = 0.5

# =============================================================================
# Notion プロパティ名マッピング
# =============================================================================
# 作品マスターDB
AW_PROP_TITLE = "作品名"
AW_PROP_IMAGE = "画像"
AW_PROP_URL = "URL"
AW_PROP_POSTED_AT = "投稿日時"
AW_PROP_STATUS = "ステータス"
AW_PROP_NEXT_SCHEDULE = "次回予定"
AW_PROP_NEW_FANS_COUNT = "はじめて反応した人の数"
AW_PROP_METRICS_REL = "時系列ログ"
AW_PROP_TAGS = "タグ"

# 時系列メトリクスDB
MS_PROP_TITLE = "ログ名"
MS_PROP_PARENT_REL = "親ツイート"
MS_PROP_MEASURED_AT = "計測日時"
MS_PROP_ELAPSED = "経過時間"
MS_PROP_IMPRESSIONS = "Impressions"
MS_PROP_LIKES = "Likes"
MS_PROP_RETWEETS = "Retweets"
MS_PROP_NEW_FANS = "New Fans"
MS_PROP_FOLLOWERS = "Followers"

# 予約投稿DB (Schedule Queue)
SQ_PROP_TITLE = "タイトル"
SQ_PROP_TEXT = "本文"
SQ_PROP_ATTACHMENTS = "添付画像"
SQ_PROP_SCHEDULED_AT = "投稿予約日時"
SQ_PROP_STATUS = "ステータス"
SQ_PROP_POSTED_URL = "投稿後URL"

# 予約投稿DBステータス定数
STATUS_SQ_SCHEDULED = "SCHEDULED"
STATUS_SQ_POSTED = "POSTED"
STATUS_SQ_FAILED = "FAILED"

# =============================================================================
# 新着イラスト自動検知モジュール設定
# =============================================================================
# 監視対象の X スクリーンネーム（@ なし）
X_SCREEN_NAME: str = os.getenv("X_SCREEN_NAME", "")

# プロフィール確認の最短・最長間隔（秒）
# 15〜30分に1回に抑え、人間がリロードする頻度と同等にする（1日48〜96回）
AUTO_DETECT_INTERVAL_MIN: int = 15 * 60   # 最短15分
AUTO_DETECT_INTERVAL_MAX: int = 30 * 60   # 最長30分

# 最終チェック時刻の永続化ファイルパス
AUTO_DETECT_STATE_FILE: str = str(
    Path(__file__).parent / ".auto_detect_last_check"
)
