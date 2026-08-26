# X Art Analytics System - トラブルシューティング及び仕様変更 履歴ドキュメント

> **作成日**: 2026-08-27  
> **対象リポジトリ**: twit_nanba  
> **ベースコミット**: `e633bd6` (first commit)  
> **対象ブランチ**: main

---

本書は、システム構築初期段階で発生した数々のエラーと、それを解決するためにシステムへ加えた変更の「意図」と「技術的背景」を記録したものです。

---

## 目次

1. [X（Twitter）認証の壁：WSL環境とBot検知の回避](#1-xtwitter認証の壁wsl環境とbot検知の回避)
2. [Notion APIの仕様変更：database から data_source への移行](#2-notion-apiの仕様変更database-から-data_source-への移行)
3. [Python 3.10 バージョン依存の仕様回避](#3-python-310-バージョン依存の仕様回避)
4. [Notionデータベースのスキーマ（選択肢）の厳格化](#4-notionデータベースのスキーマ選択肢の厳格化)
5. [新着イラスト自動検知モジュールの追加](#5-新着イラスト自動検知モジュールの追加)
6. [変更ファイル一覧と詳細差分](#6-変更ファイル一覧と詳細差分)
7. [総括](#7-総括)

---

## 1. X（Twitter）認証の壁：WSL環境とBot検知の回避

### 【事象】

初期仕様の `setup_auth.py` はブラウザの画面（GUI）を立ち上げてユーザーに手動ログインさせる設計でしたが、WSL環境では画面描画（X11/WSLg）が正常に機能せず進行不能になりました。

代替としてターミナル入力型のヘッドレスログインスクリプトを試行しましたが、X側のBot検知（Cloudflare等）によりログインフォームの描画がブロックされ、タイムアウトしました。

### 【変更内容と意図】

**変更**: Playwrightを用いた自動・半自動ログイン処理を**完全に破棄**し、普段使っているブラウザから直接Cookie（`auth_token`, `ct0`）を抽出して `auth_state.json` を生成する `generate_auth.py` を新規作成しました。

**意図**: スクリプトによるログイン試行自体を行わないことで、X側の強固なBot検知を完全にバイパスし、環境（WSLやGUIの有無）に一切依存せず確実かつ安全に認証セッションを確立するためです。

### 【技術的変更の詳細 — `setup_auth.py`】

**変更前（97行）**: Playwright非同期APIによるGUIログインフロー

```python
# 旧: Playwrightでブラウザを起動し手動ログインを待機
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=False, args=["--no-sandbox"])
    context = await browser.new_context(viewport={"width": 1280, "height": 900}, ...)
    page = await context.new_page()
    await page.goto("https://x.com/login")
    # ユーザーがログインするのをEnterキーで待機
    await asyncio.get_event_loop().run_in_executor(None, input)
    await context.storage_state(path=str(output_file))
```

**変更後（60行）**: Cookie直接入力によるセッション生成

```python
# 新: ターミナルでCookieを入力し、auth_state.jsonを直接生成
def main():
    auth_token = input("1. auth_token の値: ").strip()
    ct0 = input("2. ct0 の値: ").strip()
    expires = int(time.time()) + 31536000  # 1年後
    storage_state = {
        "cookies": [
            {"name": "auth_token", "value": auth_token, "domain": ".x.com", ...},
            {"name": "ct0", "value": ct0, "domain": ".x.com", ...},
        ],
        "origins": []
    }
    with open("./auth_state.json", "w") as f:
        json.dump(storage_state, f, indent=2)
```

**削除された依存**:
- `argparse` — コマンドライン引数パーサ
- `asyncio` — 非同期イベントループ
- `playwright.async_api` — ブラウザ自動操作ライブラリ

**追加された依存**:
- `json` — JSON生成
- `time` — UNIX時間計算（Cookie有効期限）

---

## 2. Notion APIの仕様変更：database から data_source への移行

### 【事象】

正しいデータベースIDを設定したにもかかわらず、Notion APIから常に `400 Bad Request (Invalid request URL)` が返却されました。調査の結果、Notionの大規模なシステムアップデートにより、インラインデータベース等の構造が従来の `database` オブジェクトから、新しい `data_source` オブジェクトへと裏側で仕様変更されていることが判明しました。

### 【変更内容と意図】

**変更 2-1 (ID特定)**: APIが `database` でフィルタリングできなくなったため、全てのオブジェクトを取得した上で、カラム（プロパティ）の名前（`"Impressions"`や`"ステータス"`など）から逆算して対象の `data_source` IDを特定する診断スクリプトを作成・実行しました。

**変更 2-2 (SDKのバイパス)**: Pythonの公式ライブラリ（`notion-client`）が自動的に古いURL（`/v1/databases/...`）を生成してしまうため、これを利用せず `client.request()` を用いて直接エンドポイント（`/v1/data_sources/{id}/query`）を叩くよう、`artworks.py`, `users.py`, `metrics_db.py` の全CRUD処理を書き換えました。

**意図**: Notionの新しいアーキテクチャ（データソース）に適合させるため。ライブラリのアップデートを待たず、生のリクエストを手動で組み立てることで強制的に通信を成立させました。

### 【技術的変更の詳細 — `notion_client_wrapper/artworks.py`】（260行変更、最大の変更ファイル）

#### クエリAPI: `databases.query()` → `client.request()` (data_sources)

**変更前**:
```python
response = client.databases.query(
    database_id=config.ARTWORKS_DB_ID,
    filter={...},
    start_cursor=start_cursor,
)
```

**変更後**:
```python
body: dict[str, Any] = {
    "filter": {
        "and": [
            {"property": config.AW_PROP_NEXT_SCHEDULE, "date": {"on_or_before": now_iso}},
            {"property": config.AW_PROP_STATUS, "select": {"does_not_equal": "COMPLETED"}},
        ]
    }
}
if start_cursor:
    body["start_cursor"] = start_cursor

response = client.request(
    path=f"data_sources/{config.ARTWORKS_DB_ID}/query",
    method="POST",
    body=body,
)
```

#### ページ作成API: `pages.create()` → `client.request("pages", "POST")`

**変更前**:
```python
page = client.pages.create(
    parent={"database_id": config.ARTWORKS_DB_ID},
    properties={...},
)
```

**変更後**:
```python
page = client.request(
    path="pages",
    method="POST",
    body={
        "parent": {"data_source_id": config.ARTWORKS_DB_ID},
        "properties": {...},
    },
)
```

> **注目**: `parent` のキーが `"database_id"` → `"data_source_id"` に変更されています。

#### ページ更新API: `pages.update()` → `client.request("pages/{id}", "PATCH")`

**変更前**:
```python
client.pages.update(page_id=page_id, properties={...})
```

**変更後**:
```python
client.request(path=f"pages/{page_id}", method="PATCH", body={"properties": {...}})
```

#### ページ取得API: `pages.retrieve()` → `client.request("pages/{id}", "GET")`

**変更前**:
```python
page = client.pages.retrieve(page_id=page_id)
```

**変更後**:
```python
page = client.request(path=f"pages/{page_id}", method="GET")
```

#### 新規追加: `find_by_tweet_url()` 関数

自動検知用に、ツイートURLでの重複チェックを行う新しいクエリ関数が追加されました:

```python
def find_by_tweet_url(url: str) -> dict[str, Any] | None:
    """ツイート URL で作品マスターDB を検索し、該当ページを返す。"""
    client = get_client()
    response = client.request(
        path=f"data_sources/{config.ARTWORKS_DB_ID}/query",
        method="POST",
        body={"filter": {"property": config.AW_PROP_URL, "url": {"equals": url}}, "page_size": 1},
    )
    results = response.get("results", [])
    return results[0] if results else None
```

#### 新規追加: `create_artwork_auto()` 関数

自動検知で検出されたイラスト投稿を、適切な開始ステージとスケジュールで登録する関数:

```python
def create_artwork_auto(url: str, title: str, posted_at: datetime, initial_stage: str) -> str:
    """自動検知用の新規作品登録。"""
    from processing.scheduler import calculate_next_schedule
    next_schedule = calculate_next_schedule(posted_at, initial_stage)
    page = client.request(
        path="pages", method="POST",
        body={
            "parent": {"data_source_id": config.ARTWORKS_DB_ID},
            "properties": {..., config.AW_PROP_STATUS: {"select": {"name": initial_stage}}, ...},
        },
    )
    return page["id"]
```

### 【技術的変更の詳細 — `notion_client_wrapper/users.py`】（110行変更）

全6関数について、上記と同様のSDKバイパス変更が適用されました:

| 関数名 | 変更前 | 変更後 |
|--------|--------|--------|
| `get_all_known_users()` | `client.databases.query(database_id=...)` | `client.request(path="data_sources/.../query", method="POST")` |
| `find_user_page()` | `client.databases.query(database_id=..., filter=...)` | `client.request(path="data_sources/.../query", method="POST", body=...)` |
| `create_user()` | `client.pages.create(parent={"database_id": ...})` | `client.request(path="pages", method="POST", body={"parent": {"data_source_id": ...}})` |
| `get_or_create_user()` | 変更なし（上記関数を呼ぶ） | 変更なし（上記関数を呼ぶ） |

また、未使用となった `timezone` のインポートが `from datetime import datetime, timezone` から `from datetime import datetime` に整理されました。

### 【技術的変更の詳細 — `notion_client_wrapper/metrics_db.py`】（14行変更）

| 変更箇所 | 内容 |
|----------|------|
| `import` | `timedelta` を先頭のimportに移動（関数内importを廃止） |
| `create_snapshot()` | `client.pages.create(parent={"database_id": ...})` → `client.request(path="pages", method="POST", body={"parent": {"data_source_id": ...}})` |
| body構造 | `properties` が `body` の内部にネストされる構造に変更 |

---

## 3. Python 3.10 バージョン依存の仕様回避

### 【事象】

診断スクリプト実行時や、日時のパース処理において、Python 3.10特有の仕様によるエラーが2件発生しました。

1. 診断用ワンライナー内で、f文字列（f-string）の中にバックスラッシュ（`\"`）を含むと `SyntaxError` になる（Python 3.11までの制約）。
2. Xから取得した投稿時刻（例: `2026-08-26T07:58:00.000Z`）をパースする際、Python 3.10の `datetime.fromisoformat()` が末尾の `Z`（UTCフラグ）に対応しておらずクラッシュした。

### 【変更内容と意図】

**変更 3-1**: 診断スクリプトにおいて、f文字列を廃止し、文字列結合（`+`）に変更しました。

**変更 3-2**: `scraper/auto_detect.py` にて、日時文字列をパースする直前に `.replace("Z", "+00:00")` の処理を追加しました。

**意図**: 実行環境のPythonバージョン（3.10）を無理にアップデートさせることなく、コード側の僅かな工夫で前方互換性を持たせ、安定稼働させるためです。

### 【技術的変更の詳細 — `scraper/auto_detect.py`（該当箇所）】

```python
# Python 3.10対応: "Z" を "+00:00" に置換してからパース
post_time_iso_fixed = post_time_iso.replace("Z", "+00:00")
posted_at = datetime.fromisoformat(post_time_iso_fixed)
if posted_at.tzinfo is None:
    posted_at = posted_at.replace(tzinfo=timezone.utc)
```

> **背景**: Python 3.11以降では `datetime.fromisoformat()` が `Z` サフィックスを自動的にUTCとして解釈しますが、Python 3.10以前では `ValueError: Invalid isoformat string` を発生させます。`.replace("Z", "+00:00")` はPython全バージョンで安全に動作する定番の回避策です。

---

## 4. Notionデータベースのスキーマ（選択肢）の厳格化

### 【事象】

データソースAPIへの通信が成功した直後、`select option "COMPLETED" not found` というバリデーションエラーが発生しました。システムが想定するステータス（`5m`, `1h`, `COMPLETED` など）が、Notion側のセレクトプロパティに事前に定義されていなかったためです。

### 【変更内容と意図】

**変更**: コード側は変更せず、NotionのUI上から「作品マスターDB」の「ステータス」プロパティに、システムが使用する全11個の選択肢を手動で追加しました。

**意図**: Notion APIは、セレクトプロパティへの値の挿入時、存在しない選択肢の「動的追加」を許可していません。システムとデータベースのスキーマ（型定義）を完全に同期させることで、データの一貫性を保つためです。

### 【追加されたステータス選択肢一覧】

| # | ステータス名 | 説明 |
|---|------------|------|
| 1 | `5m` | 投稿後5分 |
| 2 | `15m` | 投稿後15分 |
| 3 | `30m` | 投稿後30分 |
| 4 | `1h` | 投稿後1時間 |
| 5 | `2h` | 投稿後2時間 |
| 6 | `4h` | 投稿後4時間 |
| 7 | `8h` | 投稿後8時間 |
| 8 | `12h` | 投稿後12時間 |
| 9 | `24h` | 投稿後24時間 |
| 10 | `48h` | 投稿後48時間 |
| 11 | `COMPLETED` | 追跡完了 |

---

## 5. 新着イラスト自動検知モジュールの追加

上記1〜4の問題を解決した後、システムに新しい機能モジュールが追加されました。

### 【新規ファイル: `scraper/auto_detect.py`】

プロフィール画面を15〜30分に1回チェックし、画像付きの新しいイラスト投稿を検知してNotionに自動登録するモジュール。

#### 主要関数

| 関数名 | 役割 |
|--------|------|
| `should_check_now()` | 前回チェックからの経過時間を判定し、15〜30分の間隔を守る |
| `save_last_check_time()` | 最終チェック時刻をファイルに永続化 |
| `calculate_initial_stage()` | 投稿からの経過時間に応じて最適な開始ステージを決定 |
| `_is_pinned_tweet()` | 固定ツイートかどうかを判定 |
| `_is_retweet()` | リツイートかどうかを判定 |
| `_has_image()` | 画像付きツイートかどうかを判定 |
| `_extract_tweet_info()` | ツイートのID・URL・投稿時刻を抽出 |
| `check_new_art_post()` | メイン検知ロジック（プロフィール走査 → DB照合 → 自動登録） |

#### 初期ステータス決定ロジック

```
投稿から 0〜5分以内に検知  → "5m" からスタート
投稿から 6〜15分以内に検知 → "15m" からスタート
投稿から 16〜30分以内に検知 → "30m" からスタート
投稿から 31分以上           → 最も近い未来のステージからスタート
```

#### シャドウバン対策設計

| 対策 | 詳細 |
|------|------|
| アクセス頻度制限 | プロフィール確認は **15〜30分に1回** のみ（1日48〜96回） |
| 対象の絞り込み | 画像付きオリジナルツイートのみ検知対象 |
| セッション共有 | メトリクス取得のブラウザを「ついで」に使用 |
| ステルス設定 | `navigator.webdriver` の無効化、ランダムビューポート |
| ランダムウェイト | 各操作間に2〜5秒のランダムな待機時間を挿入 |

### 【変更ファイル: `main.py`】（38行変更）

メインフローに自動検知ステップ（ステップ0）を追加:

```python
from scraper.auto_detect import should_check_now, check_new_art_post

async def run(headless: bool = True) -> None:
    # ─── 0. 新着チェックが必要か判定 ───
    need_auto_detect = should_check_now()

    # 対象作品がなくても、新着チェックが必要ならブラウザを起動
    if not due_pages and not need_auto_detect:
        logger.info("対象作品なし & 新着チェック不要 — 無負荷終了")
        return

    # ブラウザ起動後、セッションを共有して新着チェック
    async with create_browser_context(headless=headless) as (context, page):
        if need_auto_detect:
            detected = await check_new_art_post(page, config.X_SCREEN_NAME)
            if detected:
                logger.info("📌 新規イラストを登録済み — 次回実行時に追跡を開始します")
```

### 【変更ファイル: `config.py`】（16行追加）

自動検知モジュール用の設定値を追加:

```python
# 監視対象の X スクリーンネーム（@ なし）
X_SCREEN_NAME: str = os.getenv("X_SCREEN_NAME", "")

# プロフィール確認の最短・最長間隔（秒）
AUTO_DETECT_INTERVAL_MIN: int = 15 * 60   # 最短15分
AUTO_DETECT_INTERVAL_MAX: int = 30 * 60   # 最長30分

# 最終チェック時刻の永続化ファイルパス
AUTO_DETECT_STATE_FILE: str = str(Path(__file__).parent / ".auto_detect_last_check")
```

### 【変更ファイル: `.env.example`】（4行追加）

```
# --- Auto-Detection ---
# 新着イラスト自動検知: 監視対象の X スクリーンネーム（@ なし）
X_SCREEN_NAME=your_screen_name
```

### 【変更ファイル: `.gitignore`】（1行追加）

```
.auto_detect_last_check
```

最終チェック時刻ファイルをバージョン管理から除外。

### 【変更ファイル: `README.md`】（36行変更）

- 「自動検知モード（推奨）」セクションの追加
- 「手動登録（オプション）」への位置づけ変更
- cron実行間隔を `* * * * *`（毎分）→ `*/5 * * * *`（5分ごと）に変更
- ディレクトリツリーに `auto_detect.py` を追加
- 「シャドウバン対策（安全設計）」セクションの追加

---

## 6. 変更ファイル一覧と詳細差分

### 変更統計サマリ

| ファイル | 追加行 | 削除行 | 変更概要 |
|----------|--------|--------|----------|
| `setup_auth.py` | 60行 | 97行 | Playwright GUI認証 → Cookie直接入力方式に全面書換え |
| `notion_client_wrapper/artworks.py` | 119行 | 141行 | SDK使用 → `client.request()` 直接呼出し + 2関数追加 |
| `notion_client_wrapper/users.py` | 37行 | 73行 | SDK使用 → `client.request()` 直接呼出し |
| `notion_client_wrapper/metrics_db.py` | 8行 | 6行 | SDK使用 → `client.request()` 直接呼出し |
| `main.py` | 28行 | 10行 | 自動検知ステップ（ステップ0）の統合 |
| `config.py` | 16行 | 0行 | 自動検知モジュール設定値の追加 |
| `README.md` | 31行 | 5行 | 自動検知モード・シャドウバン対策の記述追加 |
| `.env.example` | 4行 | 0行 | `X_SCREEN_NAME` 環境変数の追加 |
| `.gitignore` | 1行 | 0行 | `.auto_detect_last_check` の除外追加 |
| **`scraper/auto_detect.py`** | **新規** | — | 新着イラスト自動検知モジュール（未追跡ファイル） |

### API移行パターン一覧

全ファイルに共通する変更パターンを整理すると:

| 操作 | 変更前 (SDK) | 変更後 (直接リクエスト) |
|------|-------------|----------------------|
| DB検索 | `client.databases.query(database_id=ID)` | `client.request(path="data_sources/{ID}/query", method="POST", body={...})` |
| ページ作成 | `client.pages.create(parent={"database_id": ID})` | `client.request(path="pages", method="POST", body={"parent": {"data_source_id": ID}})` |
| ページ更新 | `client.pages.update(page_id=ID, properties={...})` | `client.request(path="pages/{ID}", method="PATCH", body={"properties": {...}})` |
| ページ取得 | `client.pages.retrieve(page_id=ID)` | `client.request(path="pages/{ID}", method="GET")` |

---

## 7. 総括

これらの変更により、本システムは以下の3つのハードルを全てクリアした、極めて堅牢な運用基盤となりました:

| ハードル | 解決策 | 対象ファイル |
|----------|--------|-------------|
| **Xの強力なスクレイピング対策** | Cookie直接抽出による認証バイパス | `setup_auth.py` |
| **Notionの最新API仕様** | SDKをバイパスし `data_source` エンドポイントへ直接通信 | `artworks.py`, `users.py`, `metrics_db.py` |
| **Python 3.10環境の制約** | `.replace("Z", "+00:00")` によるISO 8601パーサ互換化 | `scraper/auto_detect.py` |

さらに、これらの基盤修正の上に**新着イラスト自動検知機能**が構築され、手動でのURL登録を不要とし、投稿から最短5分でメトリクス追跡を自動開始する全自動パイプラインが実現されました。

---

> **注記**: 本ドキュメントは `git diff` (コミット `e633bd6` からの未ステージ変更) および新規未追跡ファイル `scraper/auto_detect.py` に基づいて作成されています。

