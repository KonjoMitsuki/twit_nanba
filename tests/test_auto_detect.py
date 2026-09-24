from datetime import datetime
from zoneinfo import ZoneInfo

import config
from scraper.auto_detect import should_check_now


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