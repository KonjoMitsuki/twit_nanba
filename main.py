"""
main.py — X Art Analytics System メインエントリポイント

cron から定期実行されることを想定したスクリプトです。
Notion の作品マスターDB から「次回予定 <= 現在時刻」の作品を取得し、
各作品について以下を実行します:

1. GraphQL 傍受でエンゲージメント数値取得
2. ユーザー照合ステージの場合:
   - いいねモーダルから反応者一覧取得
   - 差集合演算で新規反応者を算出・登録
3. 時系列メトリクスDBにスナップショット保存
4. 次ステージへの状態遷移

使い方:
    python main.py
    python main.py --no-headless  # ブラウザを表示して実行
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone

import config
from notion_client_wrapper import artworks, metrics_db
from notion_client_wrapper import schedule_queue
from processing import scheduler, new_fans
from storage import fans_db
from scraper.browser import create_browser_context, random_wait
from scraper.metrics import fetch_metrics
from scraper.fans import fetch_likers
from scraper.auto_detect import should_check_now, check_new_art_post
from scraper.poster import post_tweet, _extract_hashtags

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main")

# httpx (Notion SDK 内部) の成功ログを抑制 — 失敗時のみ表示
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def process_artwork(
    page,
    artwork_info: dict,
    known_users: set[str],
) -> set[str]:
    """単一作品の計測処理を実行する。

    Args:
        page: Playwright の Page オブジェクト。
        artwork_info: artworks.extract_artwork_info() で取得した作品情報辞書。
        known_users: SQLiteに保存された既知ユーザー集合（参照渡しで更新される）。

    Returns:
        set[str]: この作品で新たに検知された新規ユーザーの集合。
    """
    page_id = artwork_info["page_id"]
    url = artwork_info["url"]
    current_status = artwork_info["status"]
    posted_at_str = artwork_info["posted_at"]
    current_new_fans_count = artwork_info["new_fans_count"]

    logger.info(
        "▶ 処理開始: %s [%s] %s",
        artwork_info["title"],
        current_status,
        url,
    )

    # ─── 1. GraphQL 傍受で数値取得 ───
    try:
        metrics = await fetch_metrics(page, url)
    except TimeoutError as e:
        logger.error("数値取得タイムアウト: %s", e)
        return set()

    await random_wait()

    # ─── 2. ユーザー照合（必要な場合のみ） ───
    stage_new_fans: set[str] = set()
    if scheduler.is_fan_collection_stage(current_status):
        logger.info("🔍 ユーザー照合ステージ: いいねモーダルを取得")

        current_likers = await fetch_likers(page, url)

        if current_likers:
            stage_new_fans = new_fans.compute_new_fans(
                current_likers, known_users
            )

            if stage_new_fans:
                now = datetime.now(timezone.utc)
                inserted_count = new_fans.register_new_fans(
                    new_fans=stage_new_fans,
                    reaction_at=now,
                    tweet_id=url.rstrip("/").split("/")[-1],
                    db_path=config.FANS_DB_PATH,
                )

                # known_users を更新（以降の処理で再利用）
                known_users.update(stage_new_fans)

                # はじめて反応した人の数を累計で更新
                updated_count = current_new_fans_count + inserted_count
                artworks.update_new_fans_count(page_id, updated_count)

                logger.info(
                    "🆕 新規反応者 %d 名を登録 (累計: %d)",
                    inserted_count,
                    updated_count,
                )
        else:
            logger.info("いいねモーダルからユーザーを取得できませんでした")
    else:
        logger.info("📊 数値のみステージ: ユーザー照合スキップ")

    # ─── 3. 時系列メトリクスDBにスナップショット保存 ───
    try:
        snapshot_page_id = metrics_db.create_snapshot(
            artwork_page_id=page_id,
            stage=current_status,
            impressions=metrics["impressions"],
            likes=metrics["likes"],
            retweets=metrics["retweets"],
            new_fans_count=len(stage_new_fans),
            followers=metrics.get("followers", 0),
        )

        # 作品の時系列ログリレーションにも追加
        artworks.add_metrics_relation(page_id, snapshot_page_id)

        logger.info(
            "📝 スナップショット保存: imp=%d, likes=%d, rt=%d, new_fans=%d",
            metrics["impressions"],
            metrics["likes"],
            metrics["retweets"],
            len(stage_new_fans),
        )
    except Exception as e:
        logger.error("スナップショット保存失敗: %s", e)

    # ─── 4. 次ステージへの状態遷移 ───
    try:
        next_stage = scheduler.get_next_stage(current_status)

        if next_stage is None:
            # COMPLETED
            artworks.update_status(page_id, "COMPLETED", None)
            logger.info("🏁 追跡完了: ステータスを COMPLETED に更新")
        else:
            # 投稿日時をパース
            posted_at = datetime.fromisoformat(posted_at_str)
            next_schedule = scheduler.calculate_next_schedule(
                posted_at, next_stage
            )
            artworks.update_status(page_id, next_stage, next_schedule)
            logger.info(
                "⏭ 次ステージ: %s (次回予定: %s)",
                scheduler.get_stage_display_name(next_stage),
                next_schedule.isoformat(),
            )
    except Exception as e:
        logger.error("状態遷移失敗: %s", e)

    return stage_new_fans


async def run(headless: bool = True) -> None:
    """メイン実行フロー。

    【フロー概要】
    0. 予約投稿チェック（Notion 予約DBから投稿対象を取得しXへ投稿）
    1. 新着イラスト自動検知（15〜30分に1回、ブラウザセッション共有）
    2. 対象作品の取得
    3. ユーザー照合の事前準備
    4. ブラウザ起動 & 各作品を処理
    """
    # ─── 0. 予約投稿の対象を取得（事前準備時間を含む） ───
    scheduled_posts: list[dict] = []
    try:
        scheduled_posts = schedule_queue.get_due_scheduled_posts(
            ahead_minutes=config.SCHEDULE_QUEUE_PRE_FETCH_MIN
        )
        if scheduled_posts:
            logger.info("📬 予約投稿対象: %d 件 (最大%d分前からの準備)", len(scheduled_posts), config.SCHEDULE_QUEUE_PRE_FETCH_MIN)
    except Exception as e:
        logger.error("予約投稿の取得に失敗: %s", e)

    # ─── 1. 新着チェックが必要か判定 ───
    need_auto_detect = should_check_now()
    need_scheduled_posts = bool(scheduled_posts)

    # ─── 2. 対象作品の取得 ───
    try:
        due_pages = artworks.get_due_artworks()
    except Exception as e:
        logger.error("Notion からの作品取得に失敗: %s", e)
        sys.exit(1)

    if not due_pages and not need_auto_detect and not need_scheduled_posts:
        time.sleep(config.NO_TARGET_WAIT_SEC)
        return

    logger.info("=" * 60)
    logger.info("X Art Analytics System 実行開始")
    logger.info("=" * 60)
    logger.info("対象作品数: %d", len(due_pages))

    # 作品情報を抽出
    artwork_list = [artworks.extract_artwork_info(p) for p in due_pages]

    # ─── 3. ユーザー照合が必要なステージがあるか確認 ───
    needs_fans = any(
        scheduler.is_fan_collection_stage(a["status"])
        for a in artwork_list
    )

    # 既知ユーザー集合を事前取得（ファン照合ステージがある場合のみ）
    known_users: set[str] = set()
    if needs_fans:
        logger.info("SQLiteから既知ユーザーを取得中...")
        try:
            known_users = fans_db.get_all_known_users(config.FANS_DB_PATH)
            logger.info("既知ユーザー数: %d", len(known_users))
        except Exception as e:
            logger.warning("既知ユーザー取得失敗（空集合で続行）: %s", e)

    # ─── 4. ブラウザ起動 & 各作品を処理 ───
    async with create_browser_context(headless=headless) as (context, page):

        # ── 予約投稿の処理 ──
        if scheduled_posts:
            for sq_page in scheduled_posts:
                sq_info = schedule_queue.extract_scheduled_post_info(sq_page)
                sq_page_id = sq_info["page_id"]
                sq_title = sq_info["title"]
                sq_text = sq_info["text"]
                sq_images = sq_info["image_urls"]
                sq_scheduled_at = sq_info.get("scheduled_at")

                # ★ 追加: 他のプロセスが拾わないようにステータスを PREPARING に変更（ロック）
                schedule_queue.mark_as_preparing(sq_page_id)

                logger.info(
                    "📤 予約投稿を準備・実行: %s (予定: %s)",
                    sq_title or "(無題)",
                    sq_scheduled_at or "即時",
                )

                try:
                    tweet_url = await post_tweet(
                        page,
                        sq_text,
                        sq_images,
                        scheduled_at_iso=sq_scheduled_at,
                    )
                except Exception as e:
                    logger.error("投稿処理で例外: %s", e)
                    tweet_url = None

                if tweet_url:
                    # 予約DBを完了状態に更新
                    schedule_queue.mark_as_posted(sq_page_id, tweet_url)

                    # 追跡対象アカウントの投稿のみ作品マスターDBに登録
                    if config.X_SCREEN_NAME and (
                        f"/{config.X_SCREEN_NAME}/" in tweet_url
                        or tweet_url.endswith(f"/{config.X_SCREEN_NAME}")
                    ):
                        now = datetime.now(timezone.utc)
                        hashtags = _extract_hashtags(sq_text)

                        artwork_page_id = artworks.create_artwork_auto(
                            url=tweet_url,
                            title=sq_title or f"作品 ({tweet_url.split('/')[-1]})",
                            posted_at=now,
                            initial_stage="5m",
                            image_urls=sq_images if sq_images else None,
                            tags=hashtags if hashtags else None,
                        )

                        logger.info(
                            "🎉 作品マスターDBに登録 → 5m 追跡開始 "
                            "(Page ID: %s)",
                            artwork_page_id,
                        )
                    else:
                        logger.info(
                            "✅ 投稿完了 (追跡対象外アカウント — "
                            "作品マスターDB登録スキップ): %s",
                            tweet_url,
                        )
                else:
                    schedule_queue.mark_as_failed(sq_page_id)
                    logger.warning(
                        "⚠️ 予約投稿失敗 → FAILED に更新: %s",
                        sq_title or sq_page_id,
                    )

                await random_wait()

        # ── 新着イラスト自動検知（ブラウザセッション共有） ──
        # メトリクス取得のためにブラウザを開いた「ついで」に
        # プロフィールを確認し、無駄なブラウザ起動を削減する
        if need_auto_detect:
            try:
                detected = await check_new_art_post(
                    page, config.X_SCREEN_NAME
                )
                if detected:
                    # 新規登録が行われた場合、対象作品リストを再取得
                    # （次回のcron実行で拾われるので、ここでは再取得不要）
                    logger.info(
                        "📌 新規イラストを登録済み — "
                        "次回実行時に追跡を開始します"
                    )
                await random_wait()
            except Exception as e:
                logger.error("新着検知処理でエラー: %s", e)

        # ── メトリクス取得 & ユーザー照合 ──
        total_new_fans: set[str] = set()

        for i, artwork_info in enumerate(artwork_list):
            logger.info(
                "─── 作品 %d/%d ───",
                i + 1,
                len(artwork_list),
            )

            new = await process_artwork(page, artwork_info, known_users)
            total_new_fans.update(new)

            # 作品間にランダムウェイト（最後の作品以外）
            if i < len(artwork_list) - 1:
                await random_wait()

    logger.info("=" * 60)
    logger.info(
        "処理完了: %d 作品, 新規反応者 %d 名",
        len(artwork_list),
        len(total_new_fans),
    )
    logger.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="X Art Analytics System — メイン計測スクリプト",
    )
    parser.add_argument(
        "--no-headless",
        action="store_true",
        help="ブラウザを表示して実行（デバッグ用）",
    )
    args = parser.parse_args()

    asyncio.run(run(headless=not args.no_headless))


if __name__ == "__main__":
    main()
