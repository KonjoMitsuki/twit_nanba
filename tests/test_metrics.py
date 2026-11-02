import asyncio
import json
from urllib.parse import urlencode

import pytest

import config
from scraper import metrics
from scraper.metrics import _extract_user_followers_count


TWEET_ID = "123456789"
TWEET_URL = f"https://x.com/example/status/{TWEET_ID}"


def tweet_result(tweet_id=TWEET_ID, likes=42):
    return {
        "__typename": "Tweet",
        "rest_id": tweet_id,
        "legacy": {"favorite_count": likes, "retweet_count": 3, "full_text": "Example"},
        "views": {"count": "1234"},
        "core": {"user_results": {"result": {"legacy": {"followers_count": 321}}}},
    }


def detail_response(*entries):
    return {"data": {"threaded_conversation_with_injections_v2": {
        "instructions": [{"type": "TimelineAddEntries", "entries": [
            {"entryId": f"tweet-{tweet_id}", "content": {"itemContent": {"tweet_results": container}}}
            for tweet_id, container in entries
        ]}],
    }}}


class FakeResponse:
    def __init__(self, body, *, operation="TweetResultByRestId", tweet_id=TWEET_ID, status=200):
        self.body = body
        self.status = status
        variable = "focalTweetId" if operation == "TweetDetail" else "tweetId"
        self.url = f"https://x.com/i/api/graphql/query/{operation}?" + urlencode({
            "variables": json.dumps({variable: tweet_id}),
        })

    async def json(self):
        return self.body


class FakePage:
    def __init__(self, *attempts):
        self.attempts = attempts
        self.visits = 0
        self.listeners = []

    def on(self, event, handler):
        assert event == "response"
        self.listeners.append(handler)

    def remove_listener(self, event, handler):
        assert event == "response"
        self.listeners.remove(handler)

    async def goto(self, url, **_kwargs):
        assert url == TWEET_URL
        responses = self.attempts[self.visits]
        self.visits += 1
        for response in responses:
            for listener in self.listeners[:]:
                await listener(response)


@pytest.fixture
def short_timeouts(monkeypatch):
    monkeypatch.setattr(config, "GRAPHQL_TIMEOUT_SEC", 0.01)
    monkeypatch.setattr(config, "GRAPHQL_RETRY_TIMEOUT_SEC", 0.01)


def test_extract_user_followers_count_from_explicit_user_path():
    tweet_result = {
        "core": {
            "user_results": {
                "result": {
                    "legacy": {
                        "followers_count": 12345,
                    }
                }
            }
        },
        "legacy": {"favorite_count": 99},
    }

    assert _extract_user_followers_count(tweet_result) == 12345


def test_extract_user_followers_count_falls_back_to_recursive_scan():
    tweet_result = {
        "data": {
            "user": {
                "result": {
                    "legacy": {
                        "followers_count": 678,
                    }
                }
            }
        }
    }

    assert _extract_user_followers_count(tweet_result) == 678


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


@pytest.mark.parametrize("container", [{}, {"result": None}])
def test_fetch_metrics_unavailable_post_fails_without_timeout_or_reload(short_timeouts, container):
    # X responds HTTP 200 with no tweet result for a post that does not exist.
    missing = FakeResponse({"data": {"tweetResult": container}})
    page = FakePage([missing], [missing])

    with pytest.raises(RuntimeError, match="投稿を取得できません"):
        asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert page.visits == 1
    assert page.listeners == []


def test_fetch_metrics_detail_missing_target_does_not_use_reply_metrics(short_timeouts):
    response = FakeResponse(detail_response(
        ("999", {"result": tweet_result("999", likes=999)}),
        (TWEET_ID, {}),
    ), operation="TweetDetail")
    page = FakePage([response], [response])

    with pytest.raises(RuntimeError, match="投稿を取得できません"):
        asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert page.visits == 1
    assert page.listeners == []


@pytest.mark.parametrize("wrapped", [False, True])
def test_fetch_metrics_selects_target_in_thread(short_timeouts, wrapped):
    target = tweet_result()
    if wrapped:
        target = {"__typename": "TweetWithVisibilityResults", "tweet": target}
    page = FakePage([FakeResponse(detail_response(
        ("999", {"result": tweet_result("999", likes=999)}),
        (TWEET_ID, {"result": target}),
    ), operation="TweetDetail")])

    result = asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert result == {"impressions": 1234, "likes": 42, "retweets": 3, "followers": 321, "tweet_text": "Example"}
    assert page.visits == 1
    assert page.listeners == []


def test_fetch_metrics_ignores_response_for_another_post(short_timeouts):
    page = FakePage([
        FakeResponse({"data": {"tweetResult": {}}}, tweet_id="999"),
        FakeResponse({"data": {"tweetResult": {"result": tweet_result("999", likes=999)}}}, tweet_id="999"),
        FakeResponse({"data": {"tweetResult": {"result": tweet_result()}}}),
    ])

    result = asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert result["likes"] == 42
    assert page.visits == 1
    assert page.listeners == []


@pytest.mark.parametrize("failure", [
    FakeResponse({"data": {"tweetResult": {}}, "errors": [{"code": 88, "message": "Rate limited"}]}),
    FakeResponse({"data": {"tweetResult": {}}}, status=429),
    FakeResponse({"data": {"tweetResult": {"unexpected": True}}}),
])
def test_fetch_metrics_retries_transient_or_unknown_response(short_timeouts, failure):
    page = FakePage([failure], [FakeResponse({"data": {"tweetResult": {"result": tweet_result()}}})])

    result = asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert result["likes"] == 42
    assert page.visits == 2
    assert page.listeners == []


def test_fetch_metrics_keeps_timeout_retry_and_cleans_listener(short_timeouts):
    page = FakePage([], [])

    with pytest.raises(TimeoutError):
        asyncio.run(metrics.fetch_metrics(page, TWEET_URL))

    assert page.visits == 2
    assert page.listeners == []


def test_fetch_metrics_does_not_use_late_response_from_timed_out_attempt(short_timeouts):
    async def run():
        released = asyncio.Event()

        class DelayedResponse(FakeResponse):
            async def json(self):
                await released.wait()
                return await super().json()

        class DelayedPage(FakePage):
            async def goto(self, url, **kwargs):
                if self.visits == 0:
                    self.visits += 1
                    self.pending = asyncio.create_task(self.listeners[0](DelayedResponse(
                        {"data": {"tweetResult": {"result": tweet_result(likes=999)}}},
                    )))
                else:
                    released.set()
                    await self.pending
                    await super().goto(url, **kwargs)

        page = DelayedPage([], [FakeResponse({"data": {"tweetResult": {"result": tweet_result()}}})])
        result = await metrics.fetch_metrics(page, TWEET_URL)
        assert result["likes"] == 42
        assert page.visits == 2
        assert page.listeners == []

    asyncio.run(run())

