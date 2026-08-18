"""
notion_client_wrapper — Notion API ラッパーパッケージ

作品マスターDB, 時系列メトリクスDB, 反応者マスターDB への
CRUD 操作を提供します。
"""

from notion_client import Client
import config

# 共有 Notion クライアントインスタンス
_client: Client | None = None


def get_client() -> Client:
    """Notion クライアントのシングルトンインスタンスを返す。"""
    global _client
    if _client is None:
        if not config.NOTION_TOKEN:
            raise ValueError(
                "NOTION_TOKEN が設定されていません。.env ファイルを確認してください。"
            )
        _client = Client(auth=config.NOTION_TOKEN)
    return _client
