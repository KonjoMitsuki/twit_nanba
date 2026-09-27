import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import config
from scraper.auto_detect import _extract_tweet_info, should_check_now


def test_auto_detect_runs_after_fixed_check_time(monkeypatch, tmp_path):
    state_file = tmp_path / "last_check"
    monkeypatch.setattr(config, "AUTO_DETECT_STATE_FILE", str(state_file))
    monkeypatch.setattr(config, "AUTO_DETECT_FIXED_CHECK_TIMES", ((12, 1),))

    now = datetime(2026, 9, 25, 12, 2, tzinfo=ZoneInfo("Asia/Tokyo"))
    last_check = datetime(
        2026, 9, 25, 11, 59, tzinfo=ZoneInfo("Asia/Tokyo")
    )
    state_file.write_text(str(last_check.timestamp()))
    monkeypatch.setattr(
        "scraper.auto_detect.datetime",
        type("FixedDateTime", (), {"now": staticmethod(lambda _tz: now)}),
    )
    monkeypatch.setattr("scraper.auto_detect.time.time", lambda: now.timestamp())

    assert should_check_now() is True


def test_auto_detect_keeps_random_interval_outside_fixed_check(monkeypatch, tmp_path):
    state_file = tmp_path / "last_check"
    monkeypatch.setattr(config, "AUTO_DETECT_STATE_FILE", str(state_file))
    monkeypatch.setattr(config, "AUTO_DETECT_FIXED_CHECK_TIMES", ((12, 1), (17, 1)))

    now = datetime(2026, 9, 25, 10, 0, tzinfo=ZoneInfo("Asia/Tokyo"))
    state_file.write_text(str(now.timestamp() - 1800))
    monkeypatch.setattr(
        "scraper.auto_detect.datetime",
        type("FixedDateTime", (), {"now": staticmethod(lambda _tz: now)}),
    )
    monkeypatch.setattr("scraper.auto_detect.time.time", lambda: now.timestamp())
    monkeypatch.setattr("scraper.auto_detect.random.randint", lambda _min, _max: 1800)

    assert should_check_now() is True


def test_extract_tweet_info_strips_query_from_tweet_id():
    class FakeTime:
        first = None

        async def count(self):
            return 1

        async def evaluate(self, _script):
            return "https://x.com/user/status/2103824446700278159?s=20"

        async def get_attribute(self, _name):
            return "2026-09-25T12:00:00.000Z"

    class EmptyLocator:
        first = None

        async def count(self):
            return 0

    class FakeTweet:
        def __init__(self):
            self.time = FakeTime()
            self.time.first = self.time
            self.empty = EmptyLocator()
            self.empty.first = self.empty

        def locator(self, selector):
            return self.time if selector == "time" else self.empty

    info = asyncio.run(_extract_tweet_info(FakeTweet()))

    assert info["tweet_id"] == "2103824446700278159"