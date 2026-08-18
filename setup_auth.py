"""
setup_auth.py — 初回認証セッション保存スクリプト

Playwright で Chromium を visible モードで起動し、ユーザーが手動で
X (Twitter) にログインした後、セッション Cookie を auth_state.json
として保存します。

以降のスクリプト実行では、保存された auth_state.json をロードすることで
ID/PW による都度ログインを回避します。

使い方:
    python setup_auth.py
    python setup_auth.py --output /path/to/auth_state.json
"""

import argparse
import asyncio
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def run(output_path: str) -> None:
    """ブラウザを起動し、手動ログイン後にセッションを保存する。"""
    print("=" * 60)
    print("X (Twitter) 認証セッション保存スクリプト")
    print("=" * 60)
    print()
    print("ブラウザが開きます。X (Twitter) にログインしてください。")
    print("ログイン完了後、ホームタイムラインが表示されたら")
    print("ターミナルに戻って Enter キーを押してください。")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        page = await context.new_page()

        # X のログインページへ遷移
        await page.goto("https://x.com/login")

        # ユーザーの操作を待機
        print("⏳ ログインを待機中...")
        print("   ログインが完了したら、ここで Enter キーを押してください。")
        print()

        # 非同期で標準入力を待つ
        await asyncio.get_event_loop().run_in_executor(None, input)

        # 現在のページが認証済みか簡易チェック
        current_url = page.url
        if "login" in current_url.lower():
            print("⚠️  まだログインページのようです。続行しますか？")
            print("   Enter で続行、Ctrl+C でキャンセル")
            await asyncio.get_event_loop().run_in_executor(None, input)

        # セッション状態を保存
        output_file = Path(output_path)
        await context.storage_state(path=str(output_file))

        print(f"✅ 認証セッションを保存しました: {output_file}")
        print()
        print("以降は main.py / register_artwork.py の実行時に")
        print("このファイルが自動的にロードされます。")

        await browser.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="X (Twitter) 認証セッション保存スクリプト",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./auth_state.json",
        help="セッションファイルの保存先パス（デフォルト: ./auth_state.json）",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run(args.output))
    except KeyboardInterrupt:
        print("\nキャンセルされました。")
        sys.exit(0)


if __name__ == "__main__":
    main()
