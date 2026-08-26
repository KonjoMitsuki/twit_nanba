"""
generate_auth.py — ブラウザのCookieから直接 auth_state.json を生成するスクリプト
"""
import json
import time
from pathlib import Path

def main():
    print("=" * 60)
    print("X (Twitter) Cookie ➔ auth_state.json 変換ツール")
    print("=" * 60)
    print("普段Xを使っているブラウザ（Chrome / Edge / Zen等）で")
    print("F12キー（開発者ツール）を開いて取得したCookieを入力してください。\n")

    auth_token = input("1. auth_token の値: ").strip()
    ct0 = input("2. ct0 の値: ").strip()

    if not auth_token or not ct0:
        print("❌ エラー: 両方の値を入力してください。")
        return

    # 1年後のUNIX時間を有効期限として設定
    expires = int(time.time()) + 31536000

    storage_state = {
        "cookies": [
            {
                "name": "auth_token",
                "value": auth_token,
                "domain": ".x.com",
                "path": "/",
                "expires": expires,
                "httpOnly": True,
                "secure": True,
                "sameSite": "None"
            },
            {
                "name": "ct0",
                "value": ct0,
                "domain": ".x.com",
                "path": "/",
                "expires": expires,
                "httpOnly": False,
                "secure": True,
                "sameSite": "Lax"
            }
        ],
        "origins": []
    }

    output_path = Path("./auth_state.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(storage_state, f, indent=2)

    print("\n" + "=" * 60)
    print(f"🎉 成功: {output_path.resolve()} を生成しました！")
    print("=" * 60)

if __name__ == "__main__":
    main()