"""
register_artwork.py — 新規作品登録 CLI

ツイート URL を指定して作品マスターDB に新規エントリを作成します。
初回ステータスは "5m"、次回予定は posted_at + 5分に設定されます。

使い方:
    python register_artwork.py <TWEET_URL> [--title TITLE] [--posted-at ISO_DATETIME]

例:
    python register_artwork.py "https://x.com/user/status/123456789" \\
        --title "夏のイラスト" \\
        --posted-at "2026-08-18T21:00:00+09:00"

    # --posted-at を省略すると現在時刻が使われます
    python register_artwork.py "https://x.com/user/status/123456789"
"""

import argparse
import sys
from datetime import datetime, timezone

from notion_client_wrapper import artworks


def main() -> None:
    parser = argparse.ArgumentParser(
        description="新規イラスト作品をNotionに登録します。",
    )
    parser.add_argument(
        "url",
        type=str,
        help="ツイートの直リンク URL（例: https://x.com/user/status/123456789）",
    )
    parser.add_argument(
        "--title",
        type=str,
        default=None,
        help="作品名。省略時はツイートURLの末尾IDが使われます。",
    )
    parser.add_argument(
        "--posted-at",
        type=str,
        default=None,
        help="投稿日時（ISO 8601形式）。省略時は現在時刻。",
    )

    args = parser.parse_args()

    # URL バリデーション
    url: str = args.url
    if "status/" not in url:
        print("エラー: 有効なツイートURLを指定してください。", file=sys.stderr)
        print("例: https://x.com/user/status/123456789", file=sys.stderr)
        sys.exit(1)

    # タイトル
    title: str = args.title or f"作品 ({url.split('/')[-1]})"

    # 投稿日時
    if args.posted_at:
        try:
            posted_at = datetime.fromisoformat(args.posted_at)
        except ValueError:
            print(
                "エラー: --posted-at は ISO 8601 形式で指定してください。",
                file=sys.stderr,
            )
            print("例: 2026-08-18T21:00:00+09:00", file=sys.stderr)
            sys.exit(1)
    else:
        posted_at = datetime.now(timezone.utc)

    # タイムゾーン情報がなければ UTC として扱う
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)

    # Notion に登録
    try:
        page_id = artworks.create_artwork(
            url=url,
            title=title,
            posted_at=posted_at,
        )
        print(f"✅ 作品を登録しました。")
        print(f"   タイトル: {title}")
        print(f"   URL: {url}")
        print(f"   投稿日時: {posted_at.isoformat()}")
        print(f"   Page ID: {page_id}")
        print(f"   ステータス: 5m（初回計測待ち）")
    except Exception as e:
        print(f"❌ 登録に失敗しました: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
