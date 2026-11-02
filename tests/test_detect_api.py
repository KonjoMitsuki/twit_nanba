import fcntl
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

import api.main as api
from scraper.auto_detect import ProfileCheckResult
from scraper.url_registration import RegistrationError

URL = "https://x.com/example/status/123"


@pytest.fixture
def detect_api(monkeypatch, tmp_path):
    monkeypatch.setattr(api, "LOCK_PATH", tmp_path / ".process.lock")
    monkeypatch.setattr(api, "_manual_detect_running", False)
    monkeypatch.setattr(api, "_last_manual_trigger_ts", 0)
    monkeypatch.setattr(api, "_manual_detect_result", None)
    monkeypatch.setattr(api.config, "X_SCREEN_NAME", "example")
    page = Mock()

    @asynccontextmanager
    async def browser(**_kwargs):
        yield Mock(), page

    monkeypatch.setattr(api, "create_browser_context", browser)
    monkeypatch.setattr(api, "random_wait", AsyncMock())
    register = AsyncMock(return_value={"status": "registered", "artwork_id": "art_123", "posted_at": "2026-11-01T12:00:00+00:00"})
    detect = AsyncMock(return_value=ProfileCheckResult(False, 123))
    monkeypatch.setattr(api, "register_post_url", register)
    monkeypatch.setattr(api, "check_new_art_post", detect)
    return TestClient(api.app), page, register, detect


def test_url_endpoint_normalizes_and_reports_registration(detect_api):
    client, page, register, detect = detect_api
    response = client.post("/api/detect/url", json={"url": URL.replace("x.com", "twitter.com") + "/photo/2?s=20"})
    assert response.status_code == 202
    assert response.json() == {"status": "started"}
    register.assert_awaited_once_with(page, URL, "example")
    detect.assert_not_awaited()
    status = client.get("/api/detect/status").json()
    assert not status["running"]
    assert status["result"]["status"] == "registered"
    lock = api._try_acquire_process_lock()
    assert lock is not None
    lock.close()


@pytest.mark.parametrize("payload", [{}, {"url": "https://evil.test/a/status/123"}, {"url": URL, "extra": True}])
def test_invalid_url_does_not_lock_or_consume_cooldown(detect_api, payload):
    client, _page, register, _detect = detect_api
    assert client.post("/api/detect/url", json=payload).status_code == 422
    assert api._last_manual_trigger_ts == 0
    register.assert_not_awaited()
    assert not api.LOCK_PATH.exists()


def test_missing_tracked_account(detect_api, monkeypatch):
    client, _page, register, _detect = detect_api
    monkeypatch.setattr(api.config, "X_SCREEN_NAME", "")
    assert client.post("/api/detect/url", json={"url": URL}).status_code == 503
    register.assert_not_awaited()


def test_profile_check_keeps_original_endpoint_and_shares_cooldown(detect_api):
    client, page, register, detect = detect_api
    assert client.post("/api/detect/trigger").status_code == 200
    detect.assert_awaited_once_with(page, "example")
    register.assert_not_awaited()
    assert client.post("/api/detect/url", json={"url": URL}).status_code == 429


def test_url_blocks_profile_during_shared_cooldown(detect_api):
    client, _page, _register, _detect = detect_api
    assert client.post("/api/detect/url", json={"url": URL}).status_code == 202
    assert client.post("/api/detect/trigger").status_code == 429


def test_collector_lock_and_running_checks_block_url_registration(detect_api, monkeypatch):
    client, _page, register, _detect = detect_api
    with open(api.LOCK_PATH, "w") as held_lock:
        fcntl.flock(held_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert client.post("/api/detect/url", json={"url": URL}).status_code == 409
    assert api._last_manual_trigger_ts == 0
    monkeypatch.setattr(api, "_manual_detect_running", True)
    assert client.post("/api/detect/url", json={"url": URL}).status_code == 409
    register.assert_not_awaited()


@pytest.mark.parametrize("error, expected", [
    (RegistrationError("画像付きの投稿URLを指定してください。"), "画像付き"),
    (RuntimeError("sensitive token detail"), "処理に失敗"),
])
def test_failure_is_reported_and_lock_is_released(detect_api, error, expected):
    client, _page, register, _detect = detect_api
    register.side_effect = error
    assert client.post("/api/detect/url", json={"url": URL}).status_code == 202
    status = client.get("/api/detect/status").json()
    assert status["running"] is False
    assert status["result"]["status"] == "failed"
    assert expected in status["result"]["message"]
    assert "sensitive token detail" not in str(status)
    lock = api._try_acquire_process_lock()
    assert lock is not None
    lock.close()
