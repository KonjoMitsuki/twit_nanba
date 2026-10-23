import pytest
from fastapi.testclient import TestClient

from api import auth
from api.main import app
from storage import app_db


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "test.db"))
    for key in [
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_ALLOWED_EMAILS",
        "SESSION_SECRET",
    ]:
        monkeypatch.delenv(key, raising=False)
    return TestClient(app, base_url="https://testserver")


def configure(monkeypatch, email="one@example.com", verified=True):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("SESSION_SECRET", "x" * 48)
    monkeypatch.setenv("GOOGLE_ALLOWED_EMAILS", "one@example.com,two@example.com")
    monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://testserver/auth/callback")

    class FakeGoogle:
        async def authorize_access_token(self, request):
            return {
                "userinfo": {
                    "sub": email,
                    "email": email,
                    "email_verified": verified,
                    "name": "Test User",
                }
            }

    monkeypatch.setattr(auth, "google_client", lambda: FakeGoogle())


def login(client):
    assert client.get("/auth/callback", follow_redirects=False).status_code == 303
    return {"X-CSRF-Token": client.get("/auth/me").json()["csrf"]}


def test_unconfigured_analytics_fails_closed_but_demo_uses_no_db(client, monkeypatch):
    assert client.get("/api/analytics/views").status_code == 503
    monkeypatch.setattr(
        app_db,
        "analysis_rows",
        lambda *args: pytest.fail("Demo must not read application data"),
    )
    assert client.post("/demo-api/query", json={"panel": {}}).status_code == 200
    assert client.get("/analytics").status_code == 200


def test_login_allowlist_verification_csrf_and_logout(client, monkeypatch):
    configure(monkeypatch)
    assert client.get("/api/analytics/views").status_code == 401
    headers = login(client)
    assert client.post("/api/analytics/views", json={}).status_code == 403
    assert (
        client.post(
            "/api/analytics/views",
            json={},
            headers=headers | {"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    response = client.post("/api/analytics/views", json={}, headers=headers)
    assert response.status_code == 201
    assert client.post("/auth/logout", headers=headers).status_code == 200
    assert client.get("/api/analytics/views").status_code == 401
    configure(monkeypatch, email="outsider@example.com")
    assert client.get("/auth/callback").status_code == 403
    configure(monkeypatch, verified=False)
    assert client.get("/auth/callback").status_code == 403


def test_private_view_crud_and_conflict(client, monkeypatch):
    configure(monkeypatch)
    headers = login(client)
    created = client.post(
        "/api/analytics/views", json={"name": "A only"}, headers=headers
    ).json()
    view_id = created["id"]
    payload = {"name": "Updated", "config": created["config"], "revision": 1}
    assert (
        client.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=headers
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=headers
        ).status_code
        == 409
    )
    configure(monkeypatch, email="two@example.com")
    other = TestClient(app, base_url="https://testserver")
    other_headers = login(other)
    assert other.get("/api/analytics/views").json()["views"] == []
    assert (
        other.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=other_headers
        ).status_code
        == 404
    )
    assert (
        other.delete(
            f"/api/analytics/views/{view_id}", headers=other_headers
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/analytics/views/{view_id}", headers=headers).status_code
        == 204
    )


def test_character_api_rejects_non_character_writes_and_handles_multiple(
    client, monkeypatch
):
    configure(monkeypatch)
    headers = login(client)
    artwork_id = app_db.create_artwork(
        tweet_id="1",
        url="https://example.com/1",
        title="Protected",
        posted_at="2026-10-01T00:00:00+00:00",
    )
    url = f"/api/artworks/{artwork_id}"
    assert (
        client.patch(
            url, json={"title": "Changed", "likes": 999}, headers=headers
        ).status_code
        == 422
    )
    response = client.patch(
        url, json={"characters": ["初音ミク", "巡音ルカ", "初音ミク"]}, headers=headers
    )
    assert response.status_code == 200
    assert response.json()["characters"] == ["初音ミク", "巡音ルカ"]
    assert (
        client.patch(url, json={"characters": []}, headers=headers).json()["characters"]
        == []
    )


def test_invalid_formulas_stages_and_numeric_domains(client, monkeypatch):
    configure(monkeypatch)
    headers = login(client)
    for panel in [
        {"stage": "99h"},
        {
            "formulas": [
                {"key": "calc_bad", "label": "Bad", "expression": "__import__(1)"}
            ]
        },
        {"source": "followers", "x": "character"},
        {"bins": 10000},
    ]:
        assert (
            client.post("/api/analytics/query", json=panel, headers=headers).status_code
            == 422
        )


def test_revoked_allowlist_and_tampered_session(client, monkeypatch):
    configure(monkeypatch)
    login(client)
    cookie = client.cookies.get("xart_session")
    client.cookies.clear()
    client.cookies.set("xart_session", cookie[:-5] + "xxxxx")
    assert client.get("/auth/me").status_code == 401
    client.cookies.clear()
    login(client)
    monkeypatch.setenv("GOOGLE_ALLOWED_EMAILS", "two@example.com,three@example.com")
    assert client.get("/api/calendar?year=2026&month=10").status_code == 401
