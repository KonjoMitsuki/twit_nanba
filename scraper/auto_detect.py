"""
scraper/auto_detect.py — 新着イラスト自動検知モジュール

自分のプロフィール画面を15〜30分に1回チェックし、
画像付きの新しいイラスト投稿を検知してNotionに自動登録する。

【安全設計（シャドウバン対策）】
- プロフィールへのアクセス頻度を15〜30分に1回に制限（1日48〜96回）
- メトリクス取得のブラウザセッションを「ついで」に共有し、無駄な通信を削減
- 画像付き投稿のみを対象とし、文字ツイート・RT・リプライは無視

【初期ステータス決定ロジック】
- 投稿から 0〜5分以内に検知  → "5m" からスタート
- 投稿から 6〜15分以内に検知 → "15m" からスタート
- 投稿から 16〜30分以内に検知 → "30m" からスタート
- 投稿から 31分以上           → 最も近い未来のステージからスタート
"""

import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.async_api import Page

import config
from notion_client_wrapper import artworks
from processing.scheduler import calculate_next_schedule

logger = logging.getLogger("auto_detect")


# ─── 間隔制御 ─────────────────────────────────────────────────


def should_check_now() -> bool:
    """前回チェックからの経過時間を判定し、チェックすべきかを返す。

    15〜30分のランダムな間隔でゲートを開く。
    最終チェック時刻はファイルに永続化し、cron 再起動にも耐える。

    Returns:
        bool: チェックすべきなら True。
    """
    state_file = Path(config.AUTO_DETECT_STATE_FILE)

    if not state_file.exists():
        # 初回起動: すぐにチェック
        logger.info("🔍 初回起動: 新着チェックを実行します")
        return True

    try:
        last_check_ts = float(state_file.read_text().strip())
    except (ValueError, OSError) as e:
        logger.warning("状態ファイルの読み込み失敗 (チェック実行): %s", e)
        return True

    elapsed = time.time() - last_check_ts

    # ランダムな間隔を決定（15〜30分）
    # 毎回同じ閾値にならないよう、チェック判定のたびにランダム生成
    threshold = random.randint(
        config.AUTO_DETECT_INTERVAL_MIN,
        config.AUTO_DETECT_INTERVAL_MAX,
    )

    if elapsed >= threshold:
        logger.info(
            "🔍 前回チェックから %d 分経過 (閾値: %d 分): チェック実行",
            int(elapsed // 60),
            threshold // 60,
        )
        return True

    logger.debug(
        "⏳ 前回チェックから %d 分経過 (閾値: %d 分): スキップ",
        int(elapsed // 60),
        threshold // 60,
    )
    return False


def save_last_check_time() -> None:
    """現在時刻を最終チェック時刻としてファイルに保存する。"""
    state_file = Path(config.AUTO_DETECT_STATE_FILE)
    try:
        state_file.write_text(str(time.time()))
    except OSError as e:
        logger.error("状態ファイルの書き込み失敗: %s", e)


# ─── 初期ステータス決定 ─────────────────────────────────────────


def calculate_initial_stage(post_time_iso: str) -> str:
    """投稿時刻と現在時刻の差分から開始ステージを決定する。

    【ロジック】
    - 投稿から 0〜5分以内   → "5m"
    - 投稿から 6〜15分以内  → "15m"
    - 投稿から 16〜30分以内 → "30m"
    - 投稿から 31分以上     → 最も近い未来のステージ

    Args:
        post_time_iso: 投稿日時（ISO 8601 形式）。

    Returns:
        str: 開始ステージ名（例: "5m", "15m", "30m"）。
    """
    post_time_iso = post_time_iso.replace("Z", "+00:00")
    post_time = datetime.fromisoformat(post_time_iso)
    if post_time.tzinfo is None:
        post_time = post_time.replace(tzinfo=timezone.utc)

    now = datetime.now(timezone.utc)
    elapsed_sec = (now - post_time).total_seconds()

    # 各ステージのオフセットと照合
    for stage in config.SCHEDULE_STAGES:
        if elapsed_sec <= stage["offset_sec"]:
            logger.info(
                "📌 経過時間 %.1f 分 → 開始ステージ: %s",
                elapsed_sec / 60,
                stage["name"],
            )
            return stage["name"]

    # 全ステージを超過（30分以上前の投稿など）→ 最後のステージ
    last_stage = config.SCHEDULE_STAGES[-1]["name"]
    logger.warning(
        "⚠️ 経過時間 %.1f 分: 全ステージ超過 → %s から開始",
        elapsed_sec / 60,
        last_stage,
    )
    return last_stage


# ─── ツイート情報抽出 ─────────────────────────────────────────


async def _is_pinned_tweet(tweet_element) -> bool:
    """ツイート要素が固定ツイートかどうかを判定する。

    固定ツイートには「固定されたポスト」「Pinned」などのラベルが
    socialContext エリアに表示される。

    Args:
        tweet_element: Playwright の Locator（article 要素）。

    Returns:
        bool: 固定ツイートなら True。
    """
    social_context = tweet_element.locator(
        "div[data-testid='socialContext']"
    )
    if await social_context.count() > 0:
        text = await social_context.first.inner_text()
        # 日本語「固定」/ 英語「Pinned」を判定
        if "固定" in text or "Pinned" in text.lower():
            return True
    return False


async def _is_retweet(tweet_element) -> bool:
    """ツイート要素がリツイートかどうかを判定する。

    RT には socialContext に「リポスト」「reposted」等のラベルが表示される。

    Args:
        tweet_element: Playwright の Locator（article 要素）。

    Returns:
        bool: リツイートなら True。
    """
    social_context = tweet_element.locator(
        "div[data-testid='socialContext']"
    )
    if await social_context.count() > 0:
        text = await social_context.first.inner_text()
        if "リポスト" in text or "repost" in text.lower():
            return True
    return False


async def _has_image(tweet_element) -> bool:
    """ツイート要素に画像が含まれているかを判定する。

    Args:
        tweet_element: Playwright の Locator（article 要素）。

    Returns:
        bool: 画像付きなら True。
    """
    photo_count = await tweet_element.locator(
        "div[data-testid='tweetPhoto']"
    ).count()
    return photo_count > 0


async def _extract_tweet_info(tweet_element) -> dict | None:
    """ツイート要素からID・URL・投稿時刻を抽出する。

    Args:
        tweet_element: Playwright の Locator（article 要素）。

    Returns:
        dict | None: 抽出成功時は以下のキーを含む辞書:
            - tweet_id: ツイート ID
            - tweet_url: ツイートの直リンク URL
            - post_time_iso: 投稿日時（ISO 8601 文字列）
            抽出失敗時は None。
    """
    try:
        time_element = tweet_element.locator("time").first
        if await time_element.count() == 0:
            return None

        # time 要素の親 <a> から URL を取得
        tweet_url = await time_element.evaluate(
            "el => el.closest('a')?.href"
        )
        if not tweet_url or "/status/" not in tweet_url:
            return None

        tweet_id = tweet_url.split("/")[-1]
        post_time_iso = await time_element.get_attribute("datetime")

        return {
            "tweet_id": tweet_id,
            "tweet_url": tweet_url,
            "post_time_iso": post_time_iso,
        }
    except Exception as e:
        logger.error("ツイート情報の抽出に失敗: %s", e)
        return None


# ─── メイン検知ロジック ─────────────────────────────────────────


async def check_new_art_post(
    page: Page,
    screen_name: str | None = None,
) -> bool:
    """プロフィール画面をチェックし、新しいイラスト投稿をNotionに自動登録する。

    【フロー】
    1. プロフィールページを開く
    2. 最新ツイートを走査（固定ツイート・RTをスキップ）
    3. 画像付きツイートを発見 → Notion DB と照合
    4. 未登録なら自動登録し、追跡スケジュールをスタート

    Args:
        page: Playwright の Page オブジェクト（セッション共有）。
        screen_name: 監視対象のスクリーンネーム。省略時は config から取得。

    Returns:
        bool: 新規イラストを検知・登録した場合 True。
    """
    _screen_name = screen_name or config.X_SCREEN_NAME
    if not _screen_name:
        logger.error(
            "X_SCREEN_NAME が設定されていません。"
            ".env に X_SCREEN_NAME=あなたのID を追加してください。"
        )
        return False

    profile_url = f"https://x.com/{_screen_name}"
    logger.info("🔍 プロフィール確認: %s", profile_url)

    try:
        await page.goto(profile_url, wait_until="domcontentloaded")
        await page.wait_for_selector(
            "article[data-testid='tweet']",
            timeout=15000,
        )
    except Exception as e:
        logger.error("プロフィールページの読み込みに失敗: %s", e)
        save_last_check_time()  # 失敗してもタイマーリセット（連続リトライ防止）
        return False

    # 最新ツイートを上から走査（最大5件）
    tweets = page.locator("article[data-testid='tweet']")
    tweet_count = await tweets.count()
    max_check = min(tweet_count, 5)

    for i in range(max_check):
        tweet = tweets.nth(i)

        # 固定ツイートをスキップ
        if await _is_pinned_tweet(tweet):
            logger.debug("📌 固定ツイートをスキップ (index=%d)", i)
            continue

        # リツイートをスキップ
        if await _is_retweet(tweet):
            logger.debug("🔄 リツイートをスキップ (index=%d)", i)
            continue

        # 画像が含まれていないツイートをスキップ
        if not await _has_image(tweet):
            logger.debug("📝 画像なしツイートをスキップ (index=%d)", i)
            # 画像なしの最新オリジナルツイート → これ以降は古いので終了
            save_last_check_time()
            return False

        # ─── 画像付きオリジナルツイートを発見 ───
        tweet_info = await _extract_tweet_info(tweet)
        if tweet_info is None:
            logger.warning("ツイート情報の抽出に失敗 (index=%d)", i)
            continue

        tweet_id = tweet_info["tweet_id"]
        tweet_url = tweet_info["tweet_url"]
        post_time_iso = tweet_info["post_time_iso"]

        logger.info(
            "🖼 画像付きツイートを発見: %s (投稿: %s)",
            tweet_id,
            post_time_iso,
        )

        # Notion DB と照合（URL ベースで重複チェック）
        if artworks.find_by_tweet_url(tweet_url):
            logger.info("✅ 登録済み: %s — スキップ", tweet_id)
            save_last_check_time()
            return False

        # ─── 未登録 → 自動登録 ───
        initial_stage = calculate_initial_stage(post_time_iso)

        # 投稿時刻をパース
        post_time_iso_fixed = post_time_iso.replace("Z", "+00:00")
        posted_at = datetime.fromisoformat(post_time_iso_fixed)
        if posted_at.tzinfo is None:
            posted_at = posted_at.replace(tzinfo=timezone.utc)

        title = f"作品 ({tweet_id})"

        page_id = artworks.create_artwork_auto(
            url=tweet_url,
            title=title,
            posted_at=posted_at,
            initial_stage=initial_stage,
        )

        logger.info(
            "🎉 新しいイラスト投稿を検知・自動登録しました: %s "
            "(開始ステージ: %s, Page ID: %s)",
            tweet_id,
            initial_stage,
            page_id,
        )

        save_last_check_time()
        return True

    # 画像付きオリジナルツイートが見つからなかった
    logger.info("ℹ️ 新しいイラスト投稿は検出されませんでした")
    save_last_check_time()
    return False
