# X Art Analytics System

X（Twitter）に投稿されたイラストのエンゲージメント（いいね・RT・インプレッション）と新規反応者を自動追跡し、Notion データベースに蓄積・分析するシステムです。

---

## 📋 システム概要

- **Playwright** による GraphQL レスポンス傍受でエンゲージメント数値を取得
- **いいねモーダル** から反応者ユーザーを抽出し、差集合演算で新規ファンを判定
- **Notion 3DB 構成**（作品マスター・時系列メトリクス・反応者マスター）に自動蓄積
- 投稿後 **48時間** を10ステージで自動追跡（5m〜48h）

---

## 🚀 セットアップ

### 1. 依存パッケージのインストール

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 環境変数の設定

```bash
cp .env.example .env
```

`.env` を編集し、以下の値を設定してください:

| 変数名 | 説明 |
|--------|------|
| `NOTION_TOKEN` | Notion Integration Token |
| `ARTWORKS_DB_ID` | 作品マスターDB のデータベースID |
| `METRICS_DB_ID` | 時系列メトリクスDB のデータベースID |
| `USERS_DB_ID` | 反応者マスターDB のデータベースID |

### 3. Notion データベースの作成

Notion に以下の3つのデータベースを手動で作成し、Integration と接続（コネクト）してください。

#### 3.1 作品マスターDB (Art Works)

| プロパティ名 | 型 |
|---|---|
| 作品名 | タイトル |
| URL | URL |
| 投稿日時 | 日付 |
| ステータス | セレクト |
| 次回予定 | 日付 |
| はじめて反応した人の数 | 数値 |
| 時系列ログ | リレーション → 時系列メトリクスDB |
| 反応ユーザー | リレーション → 反応者マスターDB |

#### 3.2 時系列メトリクスDB (Metrics Snapshots)

| プロパティ名 | 型 |
|---|---|
| ログ名 | タイトル |
| 親ツイート | リレーション → 作品マスターDB |
| 計測日時 | 日付 |
| 経過時間 | セレクト |
| Impressions | 数値 |
| Likes | 数値 |
| Retweets | 数値 |
| New Fans | 数値 |

#### 3.3 反応者マスターDB (User Master)

| プロパティ名 | 型 |
|---|---|
| ユーザーID | タイトル |
| 初回反応日時 | 日付 |
| 初回反応作品 | リレーション → 作品マスターDB |

> **💡 データベースIDの取得方法**: Notion でデータベースを開き、URLの `https://www.notion.so/xxxxx?v=yyyyy` の `xxxxx` 部分がデータベースIDです。

### 4. X (Twitter) 認証セッションの保存

```bash
python setup_auth.py
```

ブラウザが開くので、X にログインしてから Enter キーを押してください。
`auth_state.json` が保存されます。

---

## 📖 使い方

### 作品の登録

新しいイラストを投稿したら、以下のコマンドで登録します:

```bash
# 投稿日時を指定して登録
python register_artwork.py "https://x.com/user/status/123456789" \
    --title "夏のイラスト" \
    --posted-at "2026-08-18T21:00:00+09:00"

# 投稿日時を省略（現在時刻が使われます）
python register_artwork.py "https://x.com/user/status/123456789"
```

### 計測の実行

```bash
# 通常実行（ヘッドレスモード）
python main.py

# デバッグ用（ブラウザ表示）
python main.py --no-headless
```

### cron による自動実行

```bash
# 1分ごとに実行（対象がなければ即終了）
* * * * * cd /path/to/twit_nanba && /path/to/python main.py >> /var/log/twit_nanba.log 2>&1
```

---

## 📊 計測スケジュール

| ステージ | 経過時間 | 取得データ |
|---------|---------|-----------|
| 5m | +5分 | 数値のみ |
| 15m | +15分 | 数値のみ |
| 30m | +30分 | 数値のみ |
| **1h** | +1時間 | **数値 + ユーザー照合** |
| 2h | +2時間 | 数値のみ |
| 3h | +3時間 | 数値のみ |
| **6h** | +6時間 | **数値 + ユーザー照合** |
| 12h | +12時間 | 数値のみ |
| **24h** | +24時間 | **数値 + ユーザー照合** |
| **48h** | +48時間 | **数値 + ユーザー照合（最終）** |

---

## 🗂 プロジェクト構成

```
twit_nanba/
├── .env                        # 環境変数
├── .env.example                # テンプレート
├── requirements.txt            # 依存パッケージ
├── README.md                   # このファイル
├── config.py                   # 設定管理
├── setup_auth.py               # 認証セッション保存
├── register_artwork.py         # 作品登録 CLI
├── main.py                     # メインスクリプト
├── scraper/
│   ├── browser.py              # ブラウザ管理
│   ├── metrics.py              # GraphQL 数値取得
│   └── fans.py                 # 反応者一覧取得
├── notion_client_wrapper/
│   ├── artworks.py             # 作品マスターDB
│   ├── metrics_db.py           # 時系列メトリクスDB
│   └── users.py                # 反応者マスターDB
└── processing/
    ├── scheduler.py            # 状態遷移エンジン
    └── new_fans.py             # 新規反応者判定
```

---

## ⚠️ 注意事項

- **auth_state.json** にはログインセッション情報が含まれます。**絶対に Git にコミットしないでください**（`.gitignore` で除外済み）。
- X のアンチスクレイピング対策により、過度な実行はアカウント制限のリスクがあります。
- セッションの有効期限が切れた場合は、再度 `setup_auth.py` を実行してください。
