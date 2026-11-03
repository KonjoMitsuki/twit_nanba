"""
scraper/metrics.py — GraphQL レスポンス傍受によるエンゲージメント数値取得

Playwright の page.on("response") を利用して、
TweetDetail / TweetResultByRestId の GraphQL レスポンスを傍受し、
いいね数・RT数・インプレッション数を抽出します。
"""

import asyncio
import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlsplit

from playwright.async_api import Page, Response

import config

logger = logging.getLogger(__name__)


class PostUnavailableError(RuntimeError):
    """X が対象投稿の不存在・閲覧不能を返した。"""


def _tweet_result_containers(
    data: dict[str, Any], tweet_id: str | None,
) -> list[dict[str, Any] | None]:
    """対象投稿の結果だけを返し、スレッド内の返信や引用は除外する。"""
    payload = data.get("data") or {}
    containers: list[dict[str, Any] | None] = []
    if "tweetResult" in payload:
        containers.append(payload["tweetResult"])

    conversation = payload.get("threaded_conversation_with_injections_v2", {})
    instructions = conversation.get("instructions", [])

    for instruction in instructions:
        if instruction.get("type") != "TimelineAddEntries":
            continue

        entries = instruction.get("entries", [])
        for entry in entries:
            entry_id = entry.get("entryId", "")
            if not entry_id.startswith("tweet-"):
                continue
            if tweet_id is not None and entry_id != f"tweet-{tweet_id}":
                continue

            content = entry.get("content", {})
            item_content = content.get("itemContent", {})
            if "tweet_results" in item_content:
                containers.append(item_content["tweet_results"])

    return containers


def _extract_tweet_data(
    data: dict[str, Any], tweet_id: str | None = None,
) -> dict[str, Any] | None:
    """TweetDetail / TweetResultByRestId から対象投稿の数値を探す。"""
    for container in _tweet_result_containers(data, tweet_id):
        if not isinstance(container, dict):
            continue
        result = container.get("result")
        if (
            isinstance(result, dict)
            and result.get("__typename") == "TweetWithVisibilityResults"
        ):
            result = result.get("tweet")
        if (
            not isinstance(result, dict)
            or not isinstance(result.get("legacy"), dict)
        ):
            continue
        result_id = result.get("rest_id") or result["legacy"].get("id_str")
        if tweet_id is None or result_id == tweet_id:
            return result

    return None


def _post_is_unavailable(data: dict[str, Any], tweet_id: str) -> bool:
    """空の投稿結果と明示的な閲覧不能応答を、未知の形式と区別する。"""
    for container in _tweet_result_containers(data, tweet_id):
        if container is None or container == {}:
            return True
        if not isinstance(container, dict) or "result" not in container:
            continue
        result = container["result"]
        if result is None or result == {}:
            return True
        if isinstance(result, dict) and result.get("__typename") in (
            "TweetTombstone", "TweetUnavailable",
        ):
            return True
    return False


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

    # X の GraphQL 構造は年々変わるため、まず投稿者情報の既知のパスを探す。
    # そこから取得できない場合に限り、レスポンス全体を再帰的に探索する。

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
    """投稿者ユーザーオブジェクトから followers_count を取得する。

    X の GraphQL 構造変更に対応:
      - 旧: core.user_results.result.legacy.followers_count
      - 新: core.user_results.result.relationship_counts.followers
            (キー名は followers / followers_count 等を試行)
    これらのパスで見つからない場合に限り、レスポンス全体を再帰的に探索する。
    """
    candidates: list[dict[str, Any]] = []

    # パス1: core.user_results.result (最も一般的)
    core_user_result = (
        tweet_result.get("core", {})
        .get("user_results", {})
        .get("result")
    )
    if isinstance(core_user_result, dict):
        candidates.append(core_user_result)

    # パス2: tweet_result.user_results.result
    user_results = tweet_result.get("user_results")
    if isinstance(user_results, dict):
        r = user_results.get("result")
        if isinstance(r, dict):
            candidates.append(r)

    # パス3: tweet_result.user / tweet_result.user.result
    user = tweet_result.get("user")
    if isinstance(user, dict):
        r = user.get("result")
        if isinstance(r, dict):
            candidates.append(r)
        candidates.append(user)

    for candidate in candidates:
        # --- 旧パス: legacy.followers_count ---
        legacy = candidate.get("legacy")
        if isinstance(legacy, dict):
            fc = legacy.get("followers_count")
            if fc is not None:
                try:
                    return int(fc)
                except (ValueError, TypeError):
                    return 0

        # --- 新パス: relationship_counts ---
        rel_counts = candidate.get("relationship_counts")
        if isinstance(rel_counts, dict):
            # キー名は followers / followers_count / follower_count 等を試行
            for key in ("followers", "followers_count", "follower_count"):
                fc = rel_counts.get(key)
                if fc is not None:
                    try:
                        return int(fc)
                    except (ValueError, TypeError):
                        continue
            # どのキーにも見つからなかった場合はダンプして調査
            logger.warning(
                "🔎 relationship_counts にフォロワー数キーが見つかりません: %s",
                rel_counts,
            )

        # --- 直接 followers_count がある場合 ---
        fc = candidate.get("followers_count")
        if fc is not None:
            try:
                return int(fc)
            except (ValueError, TypeError):
                return 0

    # 全探索フォールバック (followers_count キーを再帰探索)
    return _find_followers_count(tweet_result)


def _find_followers_count(value: Any) -> int:
    """GraphQL レスポンス内の followers_count / followers を再帰探索する。"""
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
    elif isinstance(value, list):
        for child in value:
            found = _find_followers_count(child)
            if found:
                return found

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
        PostUnavailableError: X が対象投稿の不存在・閲覧不能を返した場合。
    """
    tweet_id_match = re.search(r"/status/(\d+)", urlsplit(tweet_url).path)
    if tweet_id_match is None:
        raise ValueError(f"投稿IDを取得できません: {tweet_url}")
    tweet_id = tweet_id_match.group(1)
    metrics_future: asyncio.Future[dict[str, Any]] | None = None

    async def _handle_response(response: Response) -> None:
        """GraphQL レスポンスのハンドラ。"""
        future = metrics_future
        if future is None or future.done():
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
            variables = json.loads(parse_qs(urlsplit(url).query).get("variables", ["{}"])[0])
            response_tweet_id = variables.get("focalTweetId") or variables.get("tweetId")
            if response_tweet_id is not None and response_tweet_id != tweet_id:
                return
            body = await response.json()
            if body.get("errors"):
                return
            tweet_result = _extract_tweet_data(body, tweet_id)
            if tweet_result is not None:
                metrics = _parse_metrics(tweet_result)
                if not future.done():
                    future.set_result(metrics)
                    logger.info(
                        "GraphQL 数値取得成功: imp=%d, likes=%d, rt=%d, followers=%d",
                        metrics["impressions"],
                        metrics["likes"],
                        metrics["retweets"],
                        metrics["followers"],
                    )
            elif response_tweet_id == tweet_id and _post_is_unavailable(body, tweet_id):
                if not future.done():
                    future.set_exception(PostUnavailableError(
                        f"投稿を取得できません（X が空の投稿結果または閲覧不能を返しました）: {tweet_url}"
                    ))
        except Exception as e:
            logger.debug("GraphQL レスポンス解析スキップ: %s", e)

    # レスポンスハンドラを登録
    page.on("response", _handle_response)

    try:
        timeouts = (
            config.GRAPHQL_TIMEOUT_SEC,
            config.GRAPHQL_RETRY_TIMEOUT_SEC,
        )
        for attempt, timeout_sec in enumerate(timeouts, start=1):
            metrics_future = asyncio.get_event_loop().create_future()

            # ツイートページへ遷移
            await page.goto(tweet_url, wait_until="domcontentloaded")

            try:
                metrics = await asyncio.wait_for(
                    metrics_future,
                    timeout=timeout_sec,
                )
                return metrics
            except asyncio.TimeoutError:
                if attempt < len(timeouts):
                    logger.warning(
                        "GraphQL応答がタイムアウト (%d/%d、%.1f秒): %s。再試行します",
                        attempt,
                        len(timeouts),
                        timeout_sec,
                        tweet_url,
                    )
                    continue
                raise TimeoutError(
                    f"GraphQL レスポンスが {timeout_sec}秒以内に取得できませんでした: "
                    f"{tweet_url}"
                )
    finally:
        # ハンドラを解除
        page.remove_listener("response", _handle_response)
