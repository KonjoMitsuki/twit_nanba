import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock
from zoneinfo import ZoneInfo

import pytest
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

import config
from scraper import auto_detect
from scraper.auto_detect import _extract_tweet_info, due_follower_slot, should_check_now


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


def test_due_follower_slot_returns_due_current_day_slot(monkeypatch, tmp_path):
    state_file = tmp_path / "follower_state"
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_STATE_FILE", str(state_file))
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_TIMES", ((12, 0), (23, 59)))

    now = datetime(2026, 9, 25, 12, 5, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert due_follower_slot(now) == "12:00"


def test_due_follower_slot_retries_previous_day_failed_slot(monkeypatch, tmp_path):
    state_file = tmp_path / "follower_state"
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_STATE_FILE", str(state_file))
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_TIMES", ((12, 0), (23, 59)))
    state_file.write_text(
        '{"2026-09-24":{"23:59":{"attempts":1,"success":false}}}',
        encoding="utf-8",
    )

    now = datetime(2026, 9, 25, 0, 5, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert due_follower_slot(now) == "23:59"


def test_due_follower_slot_skips_completed_and_exhausted_slots(monkeypatch, tmp_path):
    state_file = tmp_path / "follower_state"
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_STATE_FILE", str(state_file))
    monkeypatch.setattr(config, "FOLLOWER_COLLECTION_TIMES", ((12, 0), (23, 59)))
    state_file.write_text(
        '{"2026-09-25":{"12:00":{"attempts":1,"success":true},'
        '"23:59":{"attempts":2,"success":false}}}',
        encoding="utf-8",
    )

    now = datetime(2026, 9, 25, 23, 59, tzinfo=ZoneInfo("Asia/Tokyo"))

    assert due_follower_slot(now) is None


@pytest.fixture
def profile_check(monkeypatch, tmp_path):
    state_file = tmp_path / "last_check"
    monkeypatch.setattr(config, "AUTO_DETECT_STATE_FILE", str(state_file))
    followers = AsyncMock(return_value=321)
    monkeypatch.setattr(auto_detect, "fetch_profile_followers", followers)
    find = Mock(return_value=None)
    create = Mock(return_value="notion-page")
    upsert = Mock(return_value="app-artwork")
    backup = Mock()
    monkeypatch.setattr(auto_detect.artworks, "find_by_tweet_url", find)
    monkeypatch.setattr(auto_detect.artworks, "create_artwork_auto", create)
    monkeypatch.setattr(auto_detect.app_db, "upsert_artwork", upsert)
    monkeypatch.setattr(auto_detect.backup_db, "backup_artwork", backup)
    monkeypatch.setattr(auto_detect, "characters_for_tags", Mock(return_value=[]))
    for name in ("_is_pinned_tweet", "_is_retweet"):
        monkeypatch.setattr(auto_detect, name, AsyncMock(return_value=False))
    monkeypatch.setattr(auto_detect, "_has_image", AsyncMock(return_value=True))
    monkeypatch.setattr(auto_detect, "_extract_tweet_info", AsyncMock(return_value={
        "tweet_id": "2116865529227128937",
        "tweet_url": "https://x.com/example/status/2116865529227128937",
        "post_time_iso": "2026-11-01T12:10:46.284Z",
        "image_urls": ["https://pbs.twimg.com/media/example.jpg"],
        "tags": [],
    }))
    return state_file, followers, find, create, upsert, backup


class DelayedProfilePage:
    """The profile shell and follower count arrive before the timeline."""

    def __init__(self, *, has_posts=True, timeouts=0):
        self.has_posts = has_posts
        self.timeouts = timeouts
        self.timeline_ready = False
        self.visits = 0

    async def goto(self, _url, **_kwargs):
        self.visits += 1
        self.timeline_ready = False

    async def wait_for_selector(self, selector, **_kwargs):
        if selector == "main":
            return
        if self.timeouts:
            self.timeouts -= 1
            raise PlaywrightTimeoutError("Timeline did not load")
        if self.has_posts:
            assert "article[data-testid='tweet']" in selector
        else:
            assert "[data-testid='emptyState']" in selector
        self.timeline_ready = True

    def locator(self, _selector):
        return Mock(
            count=AsyncMock(side_effect=lambda: int(self.timeline_ready and self.has_posts)),
        )


@pytest.mark.parametrize("timeouts", [0, 1])
def test_profile_check_waits_for_delayed_posts_and_registers(profile_check, timeouts):
    state_file, _followers, _find, create, upsert, backup = profile_check
    page = DelayedProfilePage(timeouts=timeouts)

    result = asyncio.run(auto_detect.check_new_art_post(page, "example"))

    assert result == auto_detect.ProfileCheckResult(True, 321)
    assert page.visits == timeouts + 1
    create.assert_called_once()
    upsert.assert_called_once()
    assert upsert.call_args.kwargs["tweet_id"] == "2116865529227128937"
    backup.assert_called_once()
    assert state_file.exists()


def test_profile_check_empty_timeline_keeps_followers(profile_check):
    state_file, _followers, find, create, upsert, backup = profile_check
    page = DelayedProfilePage(has_posts=False)

    result = asyncio.run(auto_detect.check_new_art_post(page, "example"))

    assert result == auto_detect.ProfileCheckResult(False, 321)
    assert page.timeline_ready
    assert page.visits == 1
    for write in (find, create, upsert, backup):
        write.assert_not_called()
    assert state_file.exists()


def test_profile_check_timeline_failure_is_not_logged_as_no_new_posts(profile_check, caplog):
    state_file, _followers, find, create, upsert, backup = profile_check
    page = DelayedProfilePage(timeouts=2)

    result = asyncio.run(auto_detect.check_new_art_post(page, "example"))

    assert result == auto_detect.ProfileCheckResult(False, 321)
    assert page.visits == 2
    assert "読み込みに失敗" in caplog.text
    assert "新しいイラスト投稿は検出されませんでした" not in caplog.text
    for write in (find, create, upsert, backup):
        write.assert_not_called()
    assert state_file.exists()
