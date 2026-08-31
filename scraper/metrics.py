"""
scraper/metrics.py — GraphQL レスポンス傍受によるエンゲージメント数値取得

Playwright の page.on("response") を利用して、
TweetDetail / TweetResultByRestId の GraphQL レスポンスを傍受し、
いいね数・RT数・インプレッション数を抽出します。
"""

import asyncio
import json
import logging
from typing import Any

from playwright.async_api import Page, Response

import config

logger = logging.getLogger(__name__)


def _extract_tweet_data(data: dict[str, Any]) -> dict[str, Any] | None:
    """GraphQL レスポンスの JSON から tweet result オブジェクトを再帰的に探索する。

    TweetDetail レスポンスは以下のような構造:
    data -> threaded_conversation_with_injections_v2 -> instructions
        -> entries -> content -> itemContent -> tweet_results -> result

    TweetResultByRestId レスポンスは:
    data -> tweetResult -> result

    Args:
        data: GraphQL レスポンスの JSON ルートオブジェクト。

    Returns:
        dict | None: tweet result オブジェクト（legacy, views を含む）。
    """
    # パターン1: TweetResultByRestId
    tweet_result = data.get("data", {}).get("tweetResult", {}).get("result")
    if tweet_result and "legacy" in tweet_result:
        return tweet_result

    # パターン2: TweetDetail (threaded_conversation)
    conversation = (
        data.get("data", {})
        .get("threaded_conversation_with_injections_v2", {})
    )
    instructions = conversation.get("instructions", [])

    for instruction in instructions:
        if instruction.get("type") != "TimelineAddEntries":
            continue

        entries = instruction.get("entries", [])
        for entry in entries:
            # フォーカルツイートのエントリを探す
            entry_id = entry.get("entryId", "")
            if not entry_id.startswith("tweet-"):
                continue

            # itemContent -> tweet_results -> result
            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            result = (
                item_content
                .get("tweet_results", {})
                .get("result", {})
            )

            if result and "legacy" in result:
                return result

    return None


def _parse_metrics(tweet_result: dict[str, Any]) -> dict[str, Any]:
    """tweet result オブジェクトからメトリクス値を抽出する。

    Args:
        tweet_result: _extract_tweet_data で取得した tweet result 辞書。

    Returns:
        dict: {impressions, likes, retweets, tweet_text} を含む辞書。
    """
    legacy = tweet_result.get("legacy", {})
    views = tweet_result.get("views", {})

    # インプレッション数は views.count (文字列の場合がある)
    impressions_raw = views.get("count", "0")
    try:
        impressions = int(impressions_raw)
    except (ValueError, TypeError):
        impressions = 0

    likes = legacy.get("favorite_count", 0)
    retweets = legacy.get("retweet_count", 0)

    # X の GraphQL 構造は年々変わるため、まず投稿者の明示的パスを優先し、
    # それが取れない場合のみ全探索フォールバックを使う。

    followers = _extract_user_followers_count(tweet_result)

    # ツイート本文（作品名として利用可能）
    full_text = legacy.get("full_text", "")
    # 先頭50文字に切り詰め
    tweet_text = full_text[:50] if full_text else ""

    return {
        "impressions": impressions,
        "likes": likes,
        "retweets": retweets,
        "followers": followers,
        "tweet_text": tweet_text,
    }


def _extract_user_followers_count(tweet_result: dict[str, Any]) -> int:
    """投稿者ユーザーオブジェクトから followers_count を優先取得する。

    X の GraphQL はユーザー情報が `core.user_results.result.legacy` に存在する
    ことが多く、こうした明示的なパスを優先した方が再帰探索の誤検知より
    安定する。見つからない場合のみ全探索フォールバックを使う。
    """
    candidates: list[Any] = []

    # --- デバッグ: tweet_result のトップレベルキーを出力 ---
    logger.info(
        "🔎 [followers debug] tweet_result top-level keys: %s",
        list(tweet_result.keys()),
    )

    core = tweet_result.get("core")
    if core is not None:
        logger.info(
            "🔎 [followers debug] core keys: %s",
            list(core.keys()) if isinstance(core, dict) else type(core).__name__,
        )
        user_results = core.get("user_results", {}) if isinstance(core, dict) else {}
        logger.info(
            "🔎 [followers debug] core.user_results keys: %s",
            list(user_results.keys()) if isinstance(user_results, dict) else type(user_results).__name__,
        )
        core_user_result = user_results.get("result") if isinstance(user_results, dict) else None
        if core_user_result is not None:
            logger.info(
                "🔎 [followers debug] core.user_results.result keys: %s",
                list(core_user_result.keys()) if isinstance(core_user_result, dict) else type(core_user_result).__name__,
            )
            if isinstance(core_user_result, dict):
                legacy_user = core_user_result.get("legacy")
                if isinstance(legacy_user, dict):
                    logger.info(
                        "🔎 [followers debug] core...legacy keys: %s",
                        list(legacy_user.keys()),
                    )
                    logger.info(
                        "🔎 [followers debug] core...legacy.followers_count = %r",
                        legacy_user.get("followers_count"),
                    )
                else:
                    logger.info(
                        "🔎 [followers debug] core...result.legacy is %s (not dict)",
                        type(legacy_user).__name__ if legacy_user is not None else "None",
                    )
            candidates.append(core_user_result)
        else:
            logger.info("🔎 [followers debug] core.user_results.result is None")
    else:
        logger.info("🔎 [followers debug] tweet_result has no 'core' key")

    user_results = tweet_result.get("user_results")
    if isinstance(user_results, dict):
        candidates.append(user_results.get("result"))

    user = tweet_result.get("user")
    if isinstance(user, dict):
        candidates.append(user.get("result"))
        candidates.append(user)

    for i, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            logger.debug(
                "🔎 [followers debug] candidate[%d] is %s, skipping",
                i, type(candidate).__name__,
            )
            continue

        legacy = candidate.get("legacy")
        if isinstance(legacy, dict):
            followers_count = legacy.get("followers_count")
            if followers_count is not None:
                logger.info(
                    "🔎 [followers debug] candidate[%d].legacy.followers_count = %r → returning",
                    i, followers_count,
                )
                try:
                    return int(followers_count)
                except (ValueError, TypeError):
                    return 0

        followers_count = candidate.get("followers_count")
        if followers_count is not None:
            logger.info(
                "🔎 [followers debug] candidate[%d].followers_count = %r → returning",
                i, followers_count,
            )
            try:
                return int(followers_count)
            except (ValueError, TypeError):
                return 0

    logger.info(
        "🔎 [followers debug] 明示パスで見つからず → 再帰フォールバック開始"
    )
    result = _find_followers_count(tweet_result)
    logger.info(
        "🔎 [followers debug] 再帰フォールバック結果: %d",
        result,
    )
    return result


def _find_followers_count(value: Any) -> int:
    """GraphQL レスポンス内の followers_count を取得する。"""
    if isinstance(value, dict):
        followers_count = value.get("followers_count")
        if followers_count is not None:
            try:
                return int(followers_count)
            except (ValueError, TypeError):
                return 0

        for child in value.values():
            followers = _find_followers_count(child)
            if followers:
                return followers
    elif isinstance(value, list):
        for child in value:
            followers = _find_followers_count(child)
            if followers:
                return followers

    return 0


async def fetch_metrics(page: Page, tweet_url: str) -> dict[str, Any]:
    """ツイートページに遷移し、GraphQL 傍受でエンゲージメント数値を取得する。

    Args:
        page: Playwright の Page オブジェクト。
        tweet_url: 対象ツイートの URL。

    Returns:
        dict: {impressions, likes, retweets, tweet_text} を含む辞書。

    Raises:
        TimeoutError: GraphQL レスポンスが制限時間内に取得できなかった場合。
    """
    metrics_future: asyncio.Future[dict[str, Any]] = asyncio.get_event_loop().create_future()

    async def _handle_response(response: Response) -> None:
        """GraphQL レスポンスのハンドラ。"""
        if metrics_future.done():
            return

        url = response.url
        # TweetDetail または TweetResultByRestId のレスポンスをフィルタ
        if "/graphql/" not in url:
            return

        if "TweetDetail" not in url and "TweetResultByRestId" not in url:
            return

        if response.status != 200:
            return

        try:
            body = await response.json()
            tweet_result = _extract_tweet_data(body)
            if tweet_result is not None:
                metrics = _parse_metrics(tweet_result)
                if not metrics_future.done():
                    metrics_future.set_result(metrics)
                    logger.info(
                        "GraphQL 数値取得成功: imp=%d, likes=%d, rt=%d, followers=%d",
                        metrics["impressions"],
                        metrics["likes"],
                        metrics["retweets"],
                        metrics["followers"],
                    )
        except Exception as e:
            logger.debug("GraphQL レスポンス解析スキップ: %s", e)

    # レスポンスハンドラを登録
    page.on("response", _handle_response)

    try:
        # ツイートページへ遷移
        await page.goto(tweet_url, wait_until="domcontentloaded")

        # GraphQL レスポンスを待機（タイムアウト付き）
        timeout_sec = config.GRAPHQL_TIMEOUT_SEC
        metrics = await asyncio.wait_for(
            metrics_future,
            timeout=timeout_sec,
        )
        return metrics

    except asyncio.TimeoutError:
        raise TimeoutError(
            f"GraphQL レスポンスが {timeout_sec}秒以内に取得できませんでした: "
            f"{tweet_url}"
        )
    finally:
        # ハンドラを解除
        page.remove_listener("response", _handle_response)
