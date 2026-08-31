# トラブルシューティング: フォロワー数が常に0になる問題 & ログノイズ削減

> **発生日**: 2026-08-31  
> **対象リポジトリ**: twit_nanba  
> **対象ファイル**: `scraper/metrics.py`, `main.py`, `tests/test_metrics.py`

---

## 目次

1. [フォロワー数が常に0になる問題](#1-フォロワー数が常に0になる問題)
   - [事象](#事象)
   - [原因調査](#原因調査)
   - [根本原因](#根本原因)
   - [対応策](#対応策)
   - [今後の構造変更への備え](#今後の構造変更への備え)
2. [cron実行時のログノイズ削減](#2-cron実行時のログノイズ削減)
   - [事象](#事象-1)
   - [対応策](#対応策-1)

---

## 1. フォロワー数が常に0になる問題

### 事象

`fetch_metrics()` で取得したエンゲージメント数値のうち、インプレッション・いいね・RTは正常に取得できるにもかかわらず、**フォロワー数だけが毎回 `0`** になっていた。

ログ出力例:
```
GraphQL 数値取得成功: imp=2997, likes=390, rt=22, followers=0
```

### 原因調査

#### 調査手法: デバッグログによるGraphQLレスポンス構造のダンプ

`_extract_user_followers_count()` 関数にINFOレベルのデバッグログを仕込み、GraphQLレスポンスの各階層のキー一覧を出力させた。

#### 調査結果: X GraphQL APIのユーザーオブジェクト構造が変更されていた

取得されたレスポンスのダンプ:

```
🔎 tweet_result top-level keys:
  ['__typename', 'cashtag_attachments', 'core', 'edit_control', ...]

🔎 core keys:
  ['user_results']

🔎 core.user_results keys:
  ['result']

🔎 core.user_results.result keys:
  ['__typename', 'action_counts', 'affiliates_highlighted_label', 'avatar',
   'banner', 'core', 'dm_permissions', 'follow_request_sent',
   'has_graduated_access', 'id', 'is_blue_verified', 'location',
   'media_permissions', 'notifications_settings', 'parody_commentary_fan_label',
   'pinned_items', 'possibly_sensitive', 'privacy', 'profile_bio',
   'profile_description_language', 'profile_image_shape', 'profile_metadata',
   'profile_translation', 'relationship_counts', 'relationship_perspectives',
   'rest_id', 'super_follow_eligible', 'super_followed_by', 'super_following',
   'tweet_counts', 'verification', 'website']

🔎 core...result.legacy is None (not dict)
🔎 明示パスで見つからず → 再帰フォールバック開始
🔎 再帰フォールバック結果: 0
```

### 根本原因

X（旧Twitter）の GraphQL API において、**ユーザーオブジェクトの構造が大幅に変更されていた**:

| 項目 | 旧構造 | 新構造 |
|------|--------|--------|
| ユーザー情報格納先 | `core.user_results.result.legacy` | `core.user_results.result` 直下（フラット化） |
| フォロワー数キー | `legacy.followers_count` | `relationship_counts.followers`（推定） |
| `legacy` フィールド | ユーザー詳細を格納する `dict` | **`None`**（廃止） |

コードは `legacy.followers_count` のパスのみを参照していたため、`legacy` が `None` の時点で取得に失敗。再帰フォールバック（`_find_followers_count`）も `followers_count` というキー名のみを探索していたため、新しい `relationship_counts.followers` を発見できなかった。

#### なぜ他のメトリクスは影響を受けなかったか

いいね数・RT数・インプレッション数は**ツイートオブジェクト**の `legacy` と `views` から取得しており、こちらの構造は変更されていない。変更されたのは**ユーザーオブジェクト**の `legacy` のみ。

```
tweet_result
├── legacy              ← ツイートの legacy（変更なし）
│   ├── favorite_count  ← いいね数 ✅
│   └── retweet_count   ← RT数 ✅
├── views
│   └── count           ← インプレッション数 ✅
└── core
    └── user_results
        └── result      ← ユーザーの result
            ├── legacy  ← None に変更 ❌（旧: followers_count がここにあった）
            └── relationship_counts  ← 新しいフォロワー数の格納先
                └── followers        ← フォロワー数 🆕
```

### 対応策

#### 変更内容と意図

**変更**: `_extract_user_followers_count()` と `_find_followers_count()` を書き換え、旧構造（`legacy.followers_count`）と新構造（`relationship_counts.followers`）の**両方**を探索するように修正。

**意図**: X の GraphQL 構造は頻繁に変更されるため、特定のパスへの依存を減らし、複数の候補パスをフォールバック付きで探索する堅牢な設計とした。今後さらに構造が変わった場合でも、WARNING ログで未知のキー構造が自動的にダンプされ、速やかに対応できるようにした。

#### `_extract_user_followers_count()` の修正

**変更前**: `legacy.followers_count` のみを参照

```python
def _extract_user_followers_count(tweet_result: dict[str, Any]) -> int:
    candidates: list[Any] = []

    core_user_result = (
        tweet_result.get("core", {})
        .get("user_results", {})
        .get("result")
    )
    if core_user_result is not None:
        candidates.append(core_user_result)

    # ... 他の候補パス ...

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        legacy = candidate.get("legacy")
        if isinstance(legacy, dict):
            followers_count = legacy.get("followers_count")  # ← ここしか見ていない
            if followers_count is not None:
                return int(followers_count)
        followers_count = candidate.get("followers_count")
        if followers_count is not None:
            return int(followers_count)

    return _find_followers_count(tweet_result)  # 再帰も followers_count のみ
```

**変更後**: `legacy.followers_count` → `relationship_counts.followers` → 直接キー の3段階探索

```python
def _extract_user_followers_count(tweet_result: dict[str, Any]) -> int:
    candidates: list[dict[str, Any]] = []

    # パス1: core.user_results.result (最も一般的)
    core_user_result = (
        tweet_result.get("core", {})
        .get("user_results", {})
        .get("result")
    )
    if isinstance(core_user_result, dict):
        candidates.append(core_user_result)

    # パス2, 3 ...（省略）

    for candidate in candidates:
        # --- 旧パス: legacy.followers_count ---
        legacy = candidate.get("legacy")
        if isinstance(legacy, dict):
            fc = legacy.get("followers_count")
            if fc is not None:
                return int(fc)

        # --- 新パス: relationship_counts ---
        rel_counts = candidate.get("relationship_counts")
        if isinstance(rel_counts, dict):
            for key in ("followers", "followers_count", "follower_count"):
                fc = rel_counts.get(key)
                if fc is not None:
                    return int(fc)
            # 未知のキー構造を自動ダンプ
            logger.warning(
                "🔎 relationship_counts にフォロワー数キーが見つかりません: %s",
                rel_counts,
            )

        # --- 直接 followers_count がある場合 ---
        fc = candidate.get("followers_count")
        if fc is not None:
            return int(fc)

    return _find_followers_count(tweet_result)
```

#### `_find_followers_count()` の修正（再帰フォールバック）

**変更前**: `followers_count` キーのみを探索

```python
def _find_followers_count(value: Any) -> int:
    if isinstance(value, dict):
        followers_count = value.get("followers_count")
        if followers_count is not None:
            return int(followers_count)
        for child in value.values():
            followers = _find_followers_count(child)
            if followers:
                return followers
    # ...
```

**変更後**: `followers_count` + `follower_count` + `followers`（整数値のみ）を探索

```python
def _find_followers_count(value: Any) -> int:
    if isinstance(value, dict):
        # followers_count (旧 API) を優先
        for key in ("followers_count", "follower_count"):
            fc = value.get(key)
            if fc is not None:
                try:
                    return int(fc)
                except (ValueError, TypeError):
                    pass

        # followers (新 API の relationship_counts.followers) — 整数値のみ
        followers_val = value.get("followers")
        if isinstance(followers_val, (int, float, str)):
            try:
                result = int(followers_val)
                if result > 0:
                    return result
            except (ValueError, TypeError):
                pass

        for child in value.values():
            found = _find_followers_count(child)
            if found:
                return found
    # ...
```

> **注意**: `followers` キーは汎用的な名前のため、値が `dict` 等の場合は無視し、整数値の場合のみフォロワー数として採用する。これにより、無関係なオブジェクト（例: followers のリスト等）を誤検知しない。

#### テストの追加 (`tests/test_metrics.py`)

新しい GraphQL API 構造に対応するテストケースを追加:

```python
def test_extract_user_followers_count_from_relationship_counts():
    """新しい X GraphQL API 構造: legacy が廃止され relationship_counts に移行。"""
    tweet_result = {
        "core": {
            "user_results": {
                "result": {
                    "__typename": "User",
                    "relationship_counts": {
                        "followers": 9876,
                        "following": 123,
                    },
                    "rest_id": "12345",
                }
            }
        },
        "legacy": {"favorite_count": 99},
    }
    assert _extract_user_followers_count(tweet_result) == 9876
```

### 今後の構造変更への備え

今回の修正には、将来の API 変更に備えた**自動検知機構**が組み込まれている:

| 状況 | 挙動 |
|------|------|
| `relationship_counts` が存在するが、既知のキー（`followers`, `followers_count`, `follower_count`）がない | `WARNING` ログで `relationship_counts` の全内容をダンプ |
| `relationship_counts` も `legacy` も存在しない | 再帰フォールバックで全ツリーを探索 |
| 再帰フォールバックでも見つからない | `followers=0` としてログ出力（`GraphQL 数値取得成功` のログで確認可能） |

今後同様の問題が発生した場合の調査手順:

1. `cron.log` で `followers=0` が継続していないか確認
2. `WARNING` ログで `relationship_counts にフォロワー数キーが見つかりません` が出ていないか確認
3. 必要に応じて `_extract_user_followers_count()` にデバッグログを追加し、`core.user_results.result` のキー一覧をダンプして新しい格納先を特定

---

## 2. cron実行時のログノイズ削減

### 事象

cron で毎分実行されるシステムにおいて、対象作品がない（無負荷の）実行でも以下の4行が毎回出力されており、ログが膨大になっていた:

```
2026-08-31 12:09:01 [INFO] main: ============================================================
2026-08-31 12:09:02 [INFO] main: X Art Analytics System 実行開始
2026-08-31 12:09:02 [INFO] httpx: HTTP Request: POST https://api.notion.com/... "HTTP/1.1 200 OK"
2026-08-31 12:09:02 [INFO] main: 対象作品なし & 新着チェック不要 — 無負荷終了
```

1日に約1,440回（毎分×24時間）この無意味なログが出力されていた。

### 対応策

3つの変更を実施:

#### 対応 2-1: 無負荷時のログ完全抑制

**変更前**: 無負荷でも「実行開始」バナーと「無負荷終了」を出力

```python
async def run(headless: bool = True) -> None:
    logger.info("=" * 60)
    logger.info("X Art Analytics System 実行開始")
    logger.info("=" * 60)

    need_auto_detect = should_check_now()
    due_pages = artworks.get_due_artworks()

    if not due_pages and not need_auto_detect:
        logger.info("対象作品なし & 新着チェック不要 — 無負荷終了")
        time.sleep(config.NO_TARGET_WAIT_SEC)
        return
```

**変更後**: 無負荷時は一切ログを出さず、対象作品がある場合のみバナーを表示

```python
async def run(headless: bool = True) -> None:
    need_auto_detect = should_check_now()
    due_pages = artworks.get_due_artworks()

    if not due_pages and not need_auto_detect:
        time.sleep(config.NO_TARGET_WAIT_SEC)
        return

    logger.info("=" * 60)
    logger.info("X Art Analytics System 実行開始")
    logger.info("=" * 60)
    logger.info("対象作品数: %d", len(due_pages))
```

**意図**: 「何もしなかった」ことを記録する必要はない。ログは「何かをした」ときだけ残すことで、ログの信号対雑音比（S/N比）を大幅に改善する。

#### 対応 2-2: httpx / httpcore の成功ログ抑制

**追加コード** (`main.py`):

```python
# httpx (Notion SDK 内部) の成功ログを抑制 — 失敗時のみ表示
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
```

**意図**: Notion SDK が内部で使用する httpx ライブラリは、全ての HTTP リクエストの成功・失敗を `INFO` レベルで記録する。正常時の `200 OK` ログは情報価値がなく、エラー時（`4xx`, `5xx`）のみ表示すれば十分。`WARNING` 以上に設定することで、正常時は無音、異常時のみ記録される。

#### 変更前後のログ出力比較

**変更前**（対象作品なしの1回の実行で4行）:
```
[INFO] main: ============================================================
[INFO] main: X Art Analytics System 実行開始
[INFO] httpx: HTTP Request: POST https://api.notion.com/... "HTTP/1.1 200 OK"
[INFO] main: 対象作品なし & 新着チェック不要 — 無負荷終了
```

**変更後**（対象作品なしの1回の実行で0行）:
```
（出力なし）
```

---

## 変更ファイル一覧

| ファイル | 変更内容 |
|----------|----------|
| `scraper/metrics.py` | `_extract_user_followers_count()`: `relationship_counts` からの取得を追加。`_find_followers_count()`: `followers` キー対応を追加。旧デバッグログの削除 |
| `main.py` | 実行開始バナーを無負荷判定の後に移動、無負荷時のログ削除、httpx/httpcore ロガーを `WARNING` に設定 |
| `tests/test_metrics.py` | 新 API 構造（`relationship_counts.followers`）のテストケース追加 |

