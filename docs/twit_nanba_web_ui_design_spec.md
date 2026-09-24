# twit_nanba Web UI 設計仕様書

## 1. 目的

現在の `twit_nanba` は、X に投稿したイラストの計測データを Notion DB に蓄積し、Notion を画面として利用している。

本仕様では、Notion をメイン UI から外し、独自 Web アプリを提供する。

主目的は次の 3 点。

1. 月間カレンダーで投稿作品を視覚的に一覧できる
2. カレンダー上で各作品の「いいね数」を確認でき、日単位でフォロワー増減を確認できる
3. 作品をクリックすると詳細ページへ遷移し、投稿後の「いいね・RT・インプレッション等の推移」をグラフで確認できる

---

## 2. 現行システムとの関係

現行リポジトリでは、主に以下のデータを取得している。

- 画像付き X ポストの自動検知
- 投稿日時
- X ポスト URL
- 画像 URL
- ハッシュタグ
- Impressions
- Likes
- Retweets
- Followers
- 新規反応者数
- 5分後〜48時間後の時系列メトリクス
- 新規反応者の SQLite 名簿
- 予約投稿

現行の `notion_client_wrapper` は Notion の作品 DB / メトリクス DB / 予約投稿 DB を直接操作している。

### 設計方針

Web UI が Notion API を直接読む構成にはしない。

以下の構成に変更する。

```text
                    ┌─────────────────────┐
                    │        X / Web      │
                    └──────────┬──────────┘
                               │
                         Playwright
                               │
                    ┌──────────▼──────────┐
                    │  Collector / Worker │
                    │  既存 Python 部分   │
                    └──────────┬──────────┘
                               │
                     Repository 層
                               │
                    ┌──────────▼──────────┐
                    │      App DB         │
                    │ SQLite → 将来Postgres│
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     FastAPI API     │
                    └──────────┬──────────┘
                               │ JSON
                    ┌──────────▼──────────┐
                    │ Next.js / TypeScript│
                    │      Web UI         │
                    └─────────────────────┘
```

Notion は移行期間中のみ残し、最終的には Web + App DB を主系統とする。

---

# 3. UI 要件

## 3.1 ダッシュボード / カレンダー

URL:

```text
/
```

初期表示は「今月」。

画面上部:

```text
┌─────────────────────────────────────────────┐
│ X Art Analytics                         ⚙   │
│                                             │
│ <   2026年9月   >       今日                │
│                                             │
│ フォロワー 12,345   今月 +284   投稿 18     │
│ 月間いいね 32,451   月間RT 1,823            │
└─────────────────────────────────────────────┘
```

その下に月間カレンダー。

---

## 3.2 カレンダー UI

参考 UI は添付画像のような、

- 月表示
- 曜日ヘッダ
- 日付セル
- 投稿画像を大きく表示

という構成とする。

基本レイアウト:

```text
┌────┬────┬────┬────┬────┬────┬────┐
│ 日 │ 月 │ 火 │ 水 │ 木 │ 金 │ 土 │
├────┼────┼────┼────┼────┼────┼────┤
│    │    │ 1  │ 2  │ 3  │ 4  │ 5  │
│    │    │    │ 🖼 │    │ 🖼 │    │
├────┼────┼────┼────┼────┼────┼────┤
│ 6  │ 7  │ 8  │ 9  │10  │11  │12  │
│    │🖼  │    │🖼  │    │    │🖼  │
├────┼────┼────┼────┼────┼────┼────┤
```

### 1 日セル

```text
┌─────────────────────┐
│ 18                  │
│                     │
│      ┌─────────┐    │
│      │         │    │
│      │ 画像    │    │
│      │         │    │
│      └─────────┘    │
│ ♥ 12,481   ↗ 483   │
│ Followers +21       │
└─────────────────────┘
```

### 表示項目

作品ごと:

- サムネイル
- いいね数
- RT数
- 投稿時刻（必要なら小さく）
- データ更新状態

日単位:

- Followers 増減
- 投稿本数

### 画像を押した場合

作品詳細ページへ遷移。

```text
/artworks/{artwork_id}
```

セル全体を押せるようにしてもよいが、スマホでは誤操作を避けるため作品カード単位でクリック可能にする。

---

# 4. カレンダー表示ルール

## 4.1 作品の所属日

`posted_at` を JST に変換し、その日付に表示する。

DB 内部では UTC 保存を推奨。

表示時に `Asia/Tokyo` へ変換する。

---

## 4.2 1日に複数作品ある場合

日セル内に複数カードを縦積みする。

例:

```text
18
┌─────────────┐
│ artwork A   │
│ 🖼           │
│ ♥ 12,481    │
└─────────────┘
┌─────────────┐
│ artwork B   │
│ 🖼           │
│ ♥ 3,284     │
└─────────────┘

Followers +21
3 posts
```

スマホでは 1 セル内の作品数が多い場合、

```text
+2 more
```

を表示し、タップでその日の作品一覧を展開する。

---

# 5. フォロワー増減

現在の作品メトリクスには `Followers` が保存されている。

ただし、作品が投稿されていない日には作品計測が発生しないため、将来の Web UI ではアカウント単位のフォロワースナップショットを別テーブルで収集する。

## account_metrics

```text
id
measured_at
followers
```

推奨取得頻度:

- 30分〜1時間に1回程度
- 既存の X 監視 / メトリクス取得処理と通信をできるだけ共用

これにより「投稿のない日でもフォロワー増減を表示可能」にする。

---

## 5.1 日次フォロワー増減の定義

その日の最後のフォロワー値:

```text
day_followers
```

前日の最後のフォロワー値:

```text
previous_day_followers
```

として、

```text
daily_delta = day_followers - previous_day_followers
```

とする。

例:

```text
9/17 最終: 12,300
9/18 最終: 12,321

→ 9/18: +21
```

データが存在しない場合:

```text
—
```

とし、`0` とは表示しない。

---

# 6. 作品詳細ページ

URL:

```text
/artworks/{artwork_id}
```

## 6.1 上部

```text
← カレンダーへ

┌─────────────────────────────────────────────┐
│                                             │
│                 作品画像                    │
│                                             │
└─────────────────────────────────────────────┘

作品名
2026/08/18 21:03 投稿

[ Xで開く ]

♥ 12,481      ↗ 483      👁 218,392
```

---

## 6.2 KPI

最低限:

- 現在 Likes
- 現在 Retweets
- 現在 Impressions
- 投稿時フォロワー
- 48h 時点 Likes
- 48h 時点 RT
- 48h 時点 Impressions
- 新規反応者数

追加候補:

- 1時間いいね数
- 24時間いいね数
- 1時間RT数
- 24時間RT数
- いいね増加速度
- インプレッション当たりいいね率

---

# 7. グラフ

作品詳細の中心機能。

## 7.1 メイン: いいね推移

X軸:

```text
投稿からの経過時間
```

Y軸:

```text
Likes
```

例:

```text
Likes
15000 ┤                         ●
12000 ┤                    ●────┘
 9000 ┤              ●─────┘
 6000 ┤        ●─────┘
 3000 ┤   ●────┘
    0 ┼────────────────────────────
       0   1h   3h   6h   12h  24h 48h
```

実際の計測点をドットで表示する。

---

## 7.2 メトリクス切替

グラフ上部:

```text
[ Likes ] [ Retweets ] [ Impressions ] [ Followers ]
```

Followers は作品そのものの推移と混同しないよう、

```text
投稿時点フォロワー数
```

として別系列にするか、独立グラフにする。

---

## 7.3 増加量モード

切り替え:

```text
[ 累積値 ] [ 増加量 ]
```

累積:

```text
Likes = 12,481
```

増加量:

```text
直前計測から +218
```

このモードで「伸び始めた時刻」を視覚的に確認できる。

---

# 8. 計測ログ一覧

グラフの下に表を表示。

```text
経過時間   計測日時          Likes    RT     Imp
--------------------------------------------------
5m        21:08              32      2      842
15m       21:18              84      6      2,103
30m       21:33             181     12      4,821
1h        22:03             392     24      9,412
2h        23:03             701     41     17,201
...
48h       翌21:03         12,481    483    218,392
```

---

# 9. 作品詳細の追加情報

表示候補:

- X 投稿 URL
- 投稿日時
- ハッシュタグ
- 画像枚数
- 新規反応者数
- 最終計測日時
- 計測完了状態
- 計測欠落の有無

ステータス:

```text
TRACKING
COMPLETED
ERROR
```

---

# 10. データモデル

Notion DB 依存をなくす場合、最低限以下のテーブルを用意する。

## artworks

```sql
CREATE TABLE artworks (
    id TEXT PRIMARY KEY,
    tweet_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    next_schedule TEXT,
    new_fans_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

---

## artwork_images

```sql
CREATE TABLE artwork_images (
    id TEXT PRIMARY KEY,
    artwork_id TEXT NOT NULL,
    image_order INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    storage_key TEXT,
    width INTEGER,
    height INTEGER,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id)
);
```

`storage_key` を用意して、将来的に画像キャッシュ / オブジェクトストレージへ移行できる設計にする。

---

## artwork_tags

```sql
CREATE TABLE artwork_tags (
    artwork_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (artwork_id, tag),
    FOREIGN KEY (artwork_id) REFERENCES artworks(id)
);
```

---

## metric_snapshots

```sql
CREATE TABLE metric_snapshots (
    id TEXT PRIMARY KEY,
    artwork_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    elapsed_seconds INTEGER NOT NULL,
    measured_at TEXT NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    retweets INTEGER NOT NULL DEFAULT 0,
    followers INTEGER,
    new_fans_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id)
);

CREATE INDEX idx_metric_artwork_time
ON metric_snapshots(artwork_id, measured_at);
```

`stage` だけでなく `elapsed_seconds` を保存する。

理由:

- `1h`
- `2h`
- `48h`

のような表示名を将来変更しても時系列計算を壊さないため。

---

## account_metrics

```sql
CREATE TABLE account_metrics (
    id TEXT PRIMARY KEY,
    measured_at TEXT NOT NULL,
    followers INTEGER NOT NULL
);

CREATE INDEX idx_account_metrics_time
ON account_metrics(measured_at);
```

---

## known_fans

現行 `fans.db` をほぼそのまま移行できる。

```sql
CREATE TABLE known_fans (
    screen_name TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    first_tweet_id TEXT
);
```

---

# 11. Repository 層

現在はコードから直接

```text
notion_client_wrapper.artworks
notion_client_wrapper.metrics_db
```

を呼んでいる。

今後はアプリケーションから DB 実装を直接意識させない。

例えば:

```python
class ArtworkRepository:
    def get_due_artworks(self): ...
    def get_by_id(self, artwork_id): ...
    def create(self, artwork): ...
    def update_status(self, ...): ...
```

実装:

```text
repositories/
├── artworks.py
├── metrics.py
├── account_metrics.py
└── fans.py
```

アダプタ:

```text
repositories/
├── sqlite/
└── notion/
```

とする。

これにより、

```text
Collector
   ↓
Repository interface
   ↓
SQLite
```

へ変更しても Collector 本体の変更量を抑えられる。

---

# 12. API 設計

Backend:

```text
FastAPI
```

を推奨。

## GET /api/calendar

```text
GET /api/calendar?year=2026&month=8
```

レスポンス例:

```json
{
  "year": 2026,
  "month": 8,
  "summary": {
    "followers": 12345,
    "followers_delta": 284,
    "posts": 18,
    "likes": 32451
  },
  "days": [
    {
      "date": "2026-08-18",
      "followers_delta": 21,
      "artworks": [
        {
          "id": "art_001",
          "title": "作品 (123456)",
          "posted_at": "2026-08-18T21:03:00+09:00",
          "image_url": "/media/art_001/1",
          "likes": 12481,
          "retweets": 483,
          "status": "COMPLETED"
        }
      ]
    }
  ]
}
```

---

## GET /api/artworks/{id}

作品基本情報 + 最新メトリクス。

---

## GET /api/artworks/{id}/metrics

時系列グラフ用。

```json
{
  "artwork_id": "art_001",
  "points": [
    {
      "elapsed_seconds": 300,
      "stage": "5m",
      "measured_at": "...",
      "likes": 32,
      "retweets": 2,
      "impressions": 842,
      "followers": 12290
    }
  ]
}
```

---

## GET /api/followers

指定期間のフォロワー推移。

```text
GET /api/followers?from=2026-08-01&to=2026-08-31
```

---

# 13. Web フロントエンド

推奨:

```text
Next.js
TypeScript
Tailwind CSS
Recharts
```

### 理由

- 月表示の UI を柔軟に作りやすい
- 詳細グラフを作りやすい
- PC / スマホレスポンシブ対応が容易
- API と画面を分離しやすい

カレンダーは FullCalendar をそのまま使うのではなく、最初は自前の CSS Grid で実装する。

理由:

添付 UI は一般的な予定管理カレンダーではなく、「画像ポートフォリオ + 分析情報」の UI だから。

---

# 14. 推奨ディレクトリ構成

```text
twit_nanba/
├── scraper/
├── processing/
├── storage/
│   ├── fans_db.py
│   ├── app_db.py
│   └── repositories/
│       ├── artworks.py
│       ├── metrics.py
│       └── account_metrics.py
│
├── notion_client_wrapper/
│   └── # 移行期間のみ使用
│
├── api/
│   ├── main.py
│   ├── routes/
│   │   ├── calendar.py
│   │   ├── artworks.py
│   │   └── followers.py
│   └── schemas/
│
├── web/
│   ├── app/
│   │   ├── page.tsx
│   │   └── artworks/
│   │       └── [id]/
│   │           └── page.tsx
│   ├── components/
│   │   ├── Calendar.tsx
│   │   ├── CalendarDay.tsx
│   │   ├── ArtworkCard.tsx
│   │   ├── MetricChart.tsx
│   │   └── SummaryBar.tsx
│   └── lib/
│
├── migrations/
│
└── docs/
    └── web_ui_design_spec.md
```

---

# 15. レスポンシブ対応

## PC

- 7列カレンダー
- 1セルあたり 1〜3作品を表示
- 画像を大きく表示
- 右上に月間サマリー

## タブレット

- 7列
- セル高さを自動調整
- 作品カードを縮小

## スマホ

2段階表示を推奨。

### 通常表示

```text
日付
画像
♥ 数
Followers Δ
```

### 複数作品

```text
画像
♥ 数

+2 more
```

タップ時にその日の作品を縦表示。

---

# 16. UI の色・デザイン方針

添付画像の雰囲気をそのままコピーするのではなく、

- 白背景
- 薄い罫線
- 日付は小さく
- 画像を主役
- 数値は小さめの UI
- hover 時だけカードを少し浮かせる
- 過度なダッシュボード感を避ける

を基本とする。

数値:

```text
♥ 12.4k
↗ 483
```

のようにコンパクトにする。

重要な分析画面では絶対値を省略しない。

例:

```text
♥ 12,481
```

---

# 17. フィルタ

MVP では以下を用意。

```text
[2026年8月] [タグ] [ステータス] [全作品]
```

将来:

- いいね数範囲
- RT数範囲
- 投稿時刻
- ハッシュタグ
- 画像枚数

---

# 18. キャッシュ

カレンダー表示は毎回 DB 全走査しない。

API で月単位に取得する。

```text
/api/calendar?year=2026&month=8
```

1 回でその月の:

- 作品
- latest likes
- latest RT
- latest impression
- daily follower delta

をまとめて返す。

作品詳細のみ、

```text
/api/artworks/{id}/metrics
```

で全時系列を取得。

---

# 19. 画像配信

現在保存している画像 URL を Web UI から直接利用する方式から、

```text
X media URL
      ↓
collector が取得
      ↓
画像キャッシュ
      ↓
Web UI
```

へ移行できる構造にする。

DB には、

```text
source_url
storage_key
```

の両方を持たせる。

これにより画像保存先を

- ローカル
- S3
- Cloudflare R2
- その他 Object Storage

へ後から変更できる。

---

# 20. データ移行

## Phase 1

現在の Notion + SQLite をそのまま使う。

Web UI だけを先に作る。

```text
Notion / backup.db
        ↓
Migration / Adapter
        ↓
API
        ↓
Web
```

目的:

- UI の完成
- デザイン調整
- データ仕様確認

---

## Phase 2

Collector から App DB にも書き込む。

```text
Collector
 ├──→ Notion
 └──→ App DB
```

この期間は両方に保存し、データを比較する。

---

## Phase 3

Web UI のデータ元を App DB に固定。

```text
Collector → App DB → API → Web
```

Notion はバックアップ / 補助 UI とする。

---

## Phase 4

問題がなければ Notion 依存を削除。

---

# 21. 現在のコードからの主な変更点

## 残す

- `scraper/browser.py`
- `scraper/metrics.py`
- `scraper/fans.py`
- `scraper/auto_detect.py`
- `processing/scheduler.py`
- `processing/new_fans.py`
- `scraper/poster.py`

## 抽象化する

- `notion_client_wrapper/artworks.py`
- `notion_client_wrapper/metrics_db.py`
- `notion_client_wrapper/schedule_queue.py`

## 新規追加

```text
storage/app_db.py
storage/repositories/
api/
web/
migrations/
```

---

# 22. 重要な設計上の注意点

## 22.1 Followers は作品メトリクスだけに依存しない

カレンダー上で日次のフォロワー増減を表示するため、

```text
account_metrics
```

を追加する。

---

## 22.2 stage と elapsed_seconds は両方保存する

`1h` などのラベルだけで計算しない。

```text
stage = "1h"
elapsed_seconds = 3600
```

のように保存する。

---

## 22.3 表示用数値と生データを分ける

DB:

```text
12481
```

UI:

```text
12.5k
```

とする。

丸め処理を DB に入れない。

---

## 22.4 データ欠損と 0 を区別する

重要。

```text
null → 計測できていない
0    → 本当に 0
```

として扱う。

---

## 22.5 時刻は UTC 保存

DB:

```text
UTC
```

表示:

```text
Asia/Tokyo
```

とする。

---

# 23. MVP

最初のバージョンでは機能を絞る。

### MVP-1

- 月間カレンダー
- 作品画像
- いいね数
- RT数
- 日次フォロワー増減
- 月移動
- 今日へ戻る
- 作品詳細ページ
- いいね推移グラフ
- RT推移グラフ
- インプレッション推移グラフ
- X 投稿へのリンク

### MVP-2

- タグフィルタ
- 月間集計
- Followers 推移
- 計測ログ一覧
- 新規反応者数

### 将来

- 投稿予約 UI
- 複数作品比較
- ハッシュタグ分析
- 投稿時刻分析
- 作品ごとのランキングではなく、自分の過去作品との比較
- 期間比較
- CSV / JSON エクスポート

---

# 24. 実装順

推奨順序:

```text
1. App DB のスキーマ確定
2. 既存 backup.db / Notion から migration
3. Repository 層を作る
4. FastAPI
5. /api/calendar
6. カレンダー UI
7. /api/artworks/{id}
8. 詳細ページ
9. グラフ
10. account_metrics の収集
11. Collector を App DB 対応
12. Notion 依存を縮小
```

---

# 25. 最終的な完成形

```text
                    X
                    │
              Playwright
                    │
                    ▼
             Python Collector
                    │
                    ▼
                App DB
        ┌───────────┼───────────┐
        │           │           │
    artworks    metrics    account_metrics
        │           │           │
        └───────────┼───────────┘
                    ▼
                 FastAPI
                    │
                    ▼
                Next.js
                    │
        ┌───────────┴────────────┐
        │                        │
   Calendar View            Artwork Detail
        │                        │
   ┌────┴─────┐             ┌────┴─────┐
   │画像      │             │大画像    │
   │Likes     │             │KPI       │
   │RT        │             │Like Chart│
   │Follower Δ│             │RT Chart  │
   └──────────┘             │Imp Chart │
                            └──────────┘
```

この構成なら「NotionをWebサイトに置き換える」だけでなく、現在の計測ロジックをほぼ維持したまま UI とデータ層を分離できる。

