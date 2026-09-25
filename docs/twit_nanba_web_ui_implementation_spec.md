# twit_nanba Web UI 実装仕様指示書
## 対象: 複数画像カルーセル / 折れ線グラフ / 日付ベースカレンダーAPI

### 0. 実装目的

現在の `twit_nanba` は、Notion と App DB を併用しながら、FastAPI + 静的 Web UI を実装済み。

今回の実装では、既存の全体構成を大きく変えず、以下の3点だけを完成させる。

1. **1つのX投稿に複数画像がある場合、作品詳細ページでカルーセル表示する**
2. **作品詳細のメトリクスグラフを棒グラフから折れ線グラフへ変更する**
3. **カレンダーAPIを「作品がある日だけ返す」方式から「その月の全日付を返す」方式へ変更する**

また、以下は今回の実装対象外とする。

- 同日投稿同士の比較機能
- 投稿ランキング
- 高度な分析ダッシュボード
- 投稿予約UIのWeb化
- Notion完全削除
- DBをSQLiteからPostgreSQLへ変更

---

# 1. 現状確認

現在の主要ファイル:

```text
storage/app_db.py
api/main.py
web/index.html
web/app.js
web/detail.html
web/detail.js
web/styles.css
tests/test_app_db.py
tests/test_migration.py
```

現状のデータモデルはすでに、

```text
artworks
  ↓
artwork_images
```

となっており、1投稿に複数画像を紐づけられる。

この設計は維持する。

---

# 2. 重要なデータ概念

必ず以下の区別を維持する。

## 2.1 1投稿 = 1 artwork

例:

```text
X投稿A
 ├─ 画像1
 ├─ 画像2
 ├─ 画像3
 └─ 画像4
```

これは `artworks` 1件。

メトリクスも1投稿単位。

```text
Likes
RT
Impressions
Followers
```

---

## 2.2 1日に複数投稿

例:

```text
2026-08-18
 ├─ 投稿A
 │   ├─ 画像1
 │   └─ 画像2
 │
 ├─ 投稿B
 │   └─ 画像1
 │
 └─ 投稿C
     └─ 画像1
```

これは `artworks` 3件。

カレンダー上では同じ日付の中に3つの投稿カードとして表示する。

この動作は今回の変更対象ではないが、絶対に壊さない。

---

# 3. カレンダーAPI改修

対象:

```text
storage/app_db.py
get_calendar()
api/main.py
```

## 3.1 現在の問題

現在の `get_calendar()` は作品が存在する日だけ `days` を生成している。

そのため、

```text
8/17 投稿あり
8/18 投稿なし
8/19 投稿あり
```

の場合、

```json
{
  "days": [
    {"date": "2026-08-17", ...},
    {"date": "2026-08-19", ...}
  ]
}
```

となる。

これを修正する。

---

# 4. calendar API の新仕様

エンドポイント:

```http
GET /api/calendar?year=2026&month=8
```

必ず対象月の1日〜末日まで、すべての日付を返す。

例えば2026年8月なら31件。

```json
{
  "year": 2026,
  "month": 8,
  "summary": {
    "followers": 12345,
    "followers_delta": 284,
    "posts": 18,
    "likes": 32451,
    "retweets": 1823
  },
  "days": [
    {
      "date": "2026-08-01",
      "followers_delta": 12,
      "artworks": []
    },
    {
      "date": "2026-08-02",
      "followers_delta": null,
      "artworks": []
    },
    {
      "date": "2026-08-03",
      "followers_delta": -4,
      "artworks": [
        {
          "id": "art_xxx",
          "title": "作品",
          "posted_at": "2026-08-03T12:00:00+00:00",
          "image_url": "https://...",
          "likes": 1200,
          "retweets": 50,
          "impressions": 18000,
          "status": "COMPLETED"
        }
      ]
    }
  ]
}
```

---

# 5. days の仕様

`days` は必ず日付順。

```text
1日
2日
3日
...
末日
```

全日付を返す。

作品がない日は:

```json
{
  "date": "2026-08-02",
  "followers_delta": 12,
  "artworks": []
}
```

とする。

---

# 6. followers_delta の定義

非常に重要。

`followers_delta` は「その日に測定されたフォロワー値の増減」。

## 6.1 当日の値

その日の JST 区間:

```text
00:00:00 JST
～
翌日00:00:00 JST
```

の間で取得された `account_metrics` のうち、**最も新しいもの**を当日の代表値とする。

## 6.2 比較対象

当日の開始時点より前に存在する `account_metrics` のうち、最も新しいものを前日以前の比較値とする。

```text
daily_delta =
  当日最後のfollowers
  -
  当日開始前の最後のfollowers
```

例:

```text
8/17 23:40 → 12,300
8/18 18:20 → 12,321
```

なら:

```text
8/18 followers_delta = +21
```

---

# 7. followers_delta が null になる条件

当日の代表値が取得できない場合:

```json
"followers_delta": null
```

とする。

0にはしない。

理由:

```text
null = データなし
0    = 増減なし
```

を区別するため。

---

# 8. 月間summaryのfollowers

対象月を無視して、

```sql
ORDER BY measured_at DESC
LIMIT 1
```

で現在時点のフォロワー数を出してはいけない。

例えば2026年8月を表示している場合、**8月末時点の最新値**を使用する。

定義:

```text
month_end_followers
=
対象月末までに存在する account_metrics の最新値
```

つまり:

```text
GET /api/calendar?year=2026&month=8
```

なら、

```text
2026-08-31 23:59:59 JST
```

以前で最も新しい `followers`。

---

# 9. 月間followers_deltaの定義

```text
対象月の最後のfollowers
-
対象月開始前の最後のfollowers
```

例:

```text
7/31 23:50 → 12,061
8/31 22:10 → 12,345

→ 8月 +284
```

どちらか一方がない場合:

```json
"followers_delta": null
```

---

# 10. 月間Likes / RT集計

既存の仕様を維持する。

対象月に投稿された各 artwork について、**その投稿の最新メトリクス**を使って集計する。

```text
monthly likes
=
8月投稿Aの最新Likes
+
8月投稿Bの最新Likes
+
...
```

既存の「最新スナップショット取得」の意図を維持する。

---

# 11. カレンダーUI改修

対象:

```text
web/app.js
web/styles.css
```

現在のフロント側が日付を生成しているロジック自体は利用してよいが、

APIから返された31日すべてを自然に扱えるようにする。

現在:

```js
const byDate = Object.fromEntries(
  data.days.map(day => [day.date, day])
);
```

という考え方はそのまま利用可能。

---

# 12. 投稿カード表示

1日複数投稿への既存対応を維持する。

```text
1投稿
↓
1カード
```

カレンダーでは:

```text
dayData.artworks
```

を投稿順に表示する。

原則:

```text
posted_at 昇順
```

---

# 13. 複数画像カルーセル

対象:

```text
web/detail.js
web/styles.css
```

## 13.1 条件

```text
artwork.images.length === 1
```

の場合:

```text
通常の1枚画像表示
```

```text
artwork.images.length >= 2
```

の場合:

```text
カルーセル
```

とする。

---

# 14. カルーセルUI

PC:

```text
             ←
       ┌─────────────┐
       │             │
       │    画像     │
       │             │
       └─────────────┘
                    →
              ● ○ ○ ○
```

スマホ:

```text
┌─────────────────┐
│                 │
│      画像       │
│                 │
└─────────────────┘

     ○ ● ○ ○

      2 / 4
```

---

# 15. カルーセル仕様

必須:

- 前へボタン
- 次へボタン
- 現在位置
- インジケータドット
- スワイプ操作
- キーボード左右キー対応（PC）
- 先頭で「前へ」を押したら先頭を維持
- 最後で「次へ」を押したら最後を維持

ループは必須ではない。

むしろ初期実装では非ループを推奨。

---

# 16. カルーセル画像の表示順

DB の

```text
image_order
```

順を厳守する。

```text
1 → 2 → 3 → 4
```

---

# 17. カルーセル画像サイズ

画像のアスペクト比を壊さない。

原則:

```css
object-fit: contain;
```

画像の縦横比を維持する。

画像をトリミングして正方形に固定しない。

---

# 18. タッチ操作

スマホで、

```text
左スワイプ → 次画像
右スワイプ → 前画像
```

を実装。

誤操作を減らすため、スワイプ距離には最低閾値を設ける。

例:

```text
50px以上
```

程度。

---

# 19. 折れ線グラフへ変更

対象:

```text
web/detail.js
web/styles.css
```

現在の `drawChart()` は棒グラフになっているため、これを折れ線グラフへ変更する。

---

# 20. グラフ対象

切り替え:

```text
Likes
RT
Impressions
```

は維持する。

モード:

```text
累積値
増加量
```

も維持する。

---

# 21. 折れ線グラフ仕様

例えばLikes:

```text
Likes
│
│                        ●
│                    ●───┘
│                ●───┘
│            ●───┘
│       ●────┘
│   ●───┘
└────────────────────────
   5m 15m 30m 1h 2h 6h 24h 48h
```

各計測点:

```text
●
```

を表示。

点と点を線でつなぐ。

---

# 22. グラフのX軸

`elapsed_seconds` を利用する。

表示ラベル:

```text
5m
15m
30m
1h
2h
...
48h
```

DBの `stage` をそのまま使ってもよいが、並び順は必ず `elapsed_seconds ASC`。

---

# 23. グラフのY軸

選択メトリクスの実値。

```text
Likes
RT
Impressions
```

それぞれ独立スケール。

---

# 24. 累積値モード

現在値をそのまま描画。

例:

```text
5m   32
15m  84
30m  181
1h   392
```

グラフ上も:

```text
32 → 84 → 181 → 392
```

---

# 25. 増加量モード

現在点と直前点の差。

例:

```text
5m   32
15m  84
30m  181
1h   392
```

なら:

```text
5m   32
15m  +52
30m  +97
1h   +211
```

---

# 26. 増加量モードの注意

最初の点は比較対象がないため、

```text
5m = 32
```

としてよい。

または、

```text
5m = null
```

としてグラフ上では最初の点をスキップしてもよい。

どちらを採用する場合もUI全体で一貫させる。

推奨:

```text
最初の点は元の累積値
```

---

# 27. グラフ実装方法

現在は外部チャートライブラリを使用していない。

今回の変更では、以下のどちらかを採用する。

### 推奨

軽量なSVG自前描画。

理由:

- 既存プロジェクトがVanilla JS
- 依存関係を増やさない
- 今のUIと統合しやすい
- レスポンシブにしやすい

または、CDN利用可能な軽量ライブラリを導入してもよい。

ただし無用に大規模なライブラリを追加しない。

---

# 28. グラフのレスポンシブ対応

PC:

```text
横幅 100%
高さ 300px 前後
```

スマホ:

```text
横幅 100%
高さ 240px 前後
```

X軸ラベルが多すぎる場合は間引いてよい。

---

# 29. グラフのホバー / タップ

各データ点を操作すると、

```text
1h

Likes
392

RT
24

Impressions
9,412
```

のようなツールチップを出せるとよい。

MVPで実装可能なら実装する。

必須ではない。

---

# 30. 既存APIは維持する

以下の既存APIを壊さない。

```text
GET /api/health
GET /api/calendar
GET /api/artworks/{artwork_id}
GET /api/artworks/{artwork_id}/metrics
GET /api/followers
```

特に、

```text
GET /api/artworks/{artwork_id}
```

の `images` 配列をそのまま詳細ページで利用する。

---

# 31. 作品詳細APIのimages

レスポンス:

```json
{
  "images": [
    {
      "id": "img_1",
      "artwork_id": "art_1",
      "image_order": 1,
      "source_url": "..."
    },
    {
      "id": "img_2",
      "artwork_id": "art_1",
      "image_order": 2,
      "source_url": "..."
    }
  ]
}
```

並び順は `image_order ASC`。

---

# 32. 画像1枚と複数枚のUI差

### 1枚

```text
┌─────────────────┐
│                 │
│      画像       │
│                 │
└─────────────────┘
```

余計な矢印やドットは出さない。

### 複数枚

```text
      ← 画像 →

      ● ○ ○ ○

      1 / 4
```

を表示。

---

# 33. 1日に複数投稿がある場合

今回の実装で絶対に以下を壊さない。

```text
dayData.artworks
```

は配列のまま。

例:

```json
{
  "date": "2026-08-18",
  "followers_delta": 21,
  "artworks": [
    {"id": "art_a"},
    {"id": "art_b"},
    {"id": "art_c"}
  ]
}
```

投稿A/B/Cはそれぞれ別作品カード。

「同日投稿比較」機能は実装しない。

---

# 34. テスト要件

最低限、以下のテストを追加する。

## Test 1: 全日付生成

31日ある月:

```text
len(days) == 31
```

---

## Test 2: 作品がない日も存在

```text
days["2026-08-02"]["artworks"] == []
```

---

## Test 3: 作品がある日

```text
days["2026-08-03"]["artworks"]
```

に作品が存在。

---

## Test 4: 作品がなくてもフォロワー増減が出る

```text
2026-08-02
artworks = []
followers_delta = 10
```

のケースをテスト。

---

## Test 5: データ不足

比較対象がなければ:

```text
followers_delta is None
```

---

## Test 6: JST境界

UTC:

```text
2026-08-31 15:30 UTC
```

はJST:

```text
2026-09-01 00:30
```

なので9月1日に入る。

既存のJST境界テストは維持・拡張する。

---

## Test 7: 複数画像順

作品に4画像:

```text
image_order = 1,2,3,4
```

の場合、API / DB取得順が:

```text
1,2,3,4
```

であること。

---

## Test 8: メトリクス時系列順

```text
elapsed_seconds
```

が昇順で返ること。

---

# 35. 手動確認項目

実装後、ブラウザで以下を確認する。

### カレンダー

- 月移動できる
- 今日へ戻れる
- 作品のない日もセルとして存在
- 投稿のない日にFollowers増減だけ表示される
- 1日に複数投稿できる
- 投稿カードをクリックできる

### 詳細

- 1枚投稿は通常画像
- 2枚以上はカルーセル
- 前後ボタン
- ドット
- 1/4などの枚数表示
- スワイプ
- 左右キー
- 元画像のアスペクト比維持

### グラフ

- Likes
- RT
- Impressions
- 累積値
- 増加量
- データ点
- 折れ線
- スマホ表示

---

# 36. 実装時に変更してよいファイル

原則:

```text
storage/app_db.py
api/main.py
web/app.js
web/detail.js
web/styles.css
tests/test_app_db.py
```

必要に応じて:

```text
tests/test_web.py
```

を追加。

---

# 37. 変更しないもの

今回の作業では以下を触らない。

```text
scraper/
processing/
notion_client_wrapper/
予約投稿ロジック
X取得ロジック
```

ただし、テストや型・互換性を維持するためにどうしても必要な最小修正は可。

---

# 38. 既存機能との互換性

以下を必ず維持する。

```text
Notion保存
App DB保存
Notion → App DB migration
既存の作品ID
tweet_id
metric_snapshots
account_metrics
```

既存データを破壊するmigrationは作らない。

---

# 39. SQL実装上の注意

SQLiteでは日時をISO 8601文字列として保存しているため、日時比較が壊れないようにする。

DB保存:

```text
UTC ISO 8601
```

表示・日付判定:

```text
Asia/Tokyo
```

とする。

---

# 40. 最終受け入れ条件

以下をすべて満たしたら今回の実装完了とする。

### カレンダー

```text
2026年8月 → 31日すべて返る
```

作品がなくても日付が消えない。

フォロワー増減は作品の有無と独立して計算される。

過去月を表示しても、未来月の最新Followersが混ざらない。

---

### 詳細画像

```text
1枚 → 単画像
2枚以上 → カルーセル
```

複数画像の順序が維持される。

---

### グラフ

```text
棒グラフ → 折れ線グラフ
```

Likes / RT / Impressions 切り替えが動作する。

累積 / 増加量が動作する。

---

### 非対象

```text
同日投稿比較
ランキング
高度な分析
```

は実装しない。

---

# 41. 実装順序

推奨順序:

```text
1. get_calendar() を全日付方式へ改修
2. followersの月次・日次境界ロジックを修正
3. calendar APIのテスト追加
4. detail.jsをカルーセル対応
5. カルーセルCSS
6. detail.jsを折れ線グラフ対応
7. グラフCSS
8. 全テスト実行
9. ブラウザ手動確認
10. README / 仕様書更新
```

---

# 42. 実装方針の最重要ポイント

今回の実装では、

**「UIだけ変える」のではなく、カレンダーのデータモデルを日付中心に正しくする。**

具体的には:

```text
旧:
作品がある日
  ↓
day生成

新:
月の日付を全部生成
  ↓
その日に作品を追加
  ↓
その日のFollower情報を追加
```

とする。

最終構造:

```text
Month
 ├─ Day 1
 │   ├─ follower_delta
 │   └─ artworks[]
 │
 ├─ Day 2
 │   ├─ follower_delta
 │   └─ artworks[]
 │
 ├─ Day 3
 │   ├─ follower_delta
 │   └─ artworks[]
 │
 ...
 └─ Day 31
```

この構造を今後のUI拡張の基礎とする。
