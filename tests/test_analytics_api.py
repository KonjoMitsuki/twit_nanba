import pytest
from fastapi.testclient import TestClient

from api.main import app
from storage import app_db


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "test.db"))
    return TestClient(app)


def profile_headers(client, index=0):
    profile = client.get("/api/profiles").json()["profiles"][index]
    return {"X-Analysis-Profile": profile["id"]}


def test_no_oauth_or_secret_is_required_and_demo_uses_no_db(client, monkeypatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "obsolete-value")
    assert client.get("/analytics").status_code == 200
    assert client.get("/api/calendar?year=2026&month=10").status_code == 200
    assert client.get("/api/analytics/views").status_code == 400
    headers = profile_headers(client)
    assert client.get("/api/analytics/views", headers=headers).status_code == 200
    assert (
        client.post("/api/analytics/query", json={}, headers=headers).status_code == 200
    )
    monkeypatch.setattr(
        app_db,
        "analysis_rows",
        lambda *args, **kwargs: pytest.fail("Demo must not read application data"),
    )
    assert client.post("/demo-api/query", json={"panel": {}}).status_code == 200
    assert client.get("/auth/login").status_code == 404


def test_profiles_can_be_added_renamed_and_selected_from_another_client(client):
    profiles = client.get("/api/profiles").json()["profiles"]
    assert [p["name"] for p in profiles] == ["利用者A", "利用者B"]
    assert client.get("/api/profiles").json()["profiles"] == profiles
    created = client.post("/api/profiles", json={"name": "  分析担当  "}).json()
    assert created["name"] == "分析担当"
    assert (
        client.post("/api/profiles", json={"name": "分析担当"}).json()["id"]
        == created["id"]
    )
    assert client.post("/api/profiles", json={"name": " "}).status_code == 422
    response = client.patch(
        f"/api/profiles/{created['id']}", json={"name": "新しい名前"}
    )
    assert response.json() == {"id": created["id"], "name": "新しい名前"}
    assert (
        client.patch(
            f"/api/profiles/{created['id']}", json={"name": "利用者A"}
        ).status_code
        == 409
    )
    assert (
        client.get(
            "/api/analytics/views", headers={"X-Analysis-Profile": "unknown"}
        ).status_code
        == 400
    )


def test_view_crud_uses_selected_profile_and_preserves_revision_checks(client):
    a, b = profile_headers(client), profile_headers(client, 1)
    created = client.post(
        "/api/analytics/views", json={"name": "A用"}, headers=a
    ).json()
    view_id = created["id"]
    assert created["locked"] is False
    assert client.get("/api/analytics/views", headers=b).json()["views"] == []
    payload = {"name": "更新", "config": created["config"], "revision": 1}
    assert (
        client.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=a
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=a
        ).status_code
        == 409
    )
    assert (
        client.patch(
            f"/api/analytics/views/{view_id}", json=payload, headers=b
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/analytics/views/{view_id}", headers=b).status_code == 404
    )
    # Deliberately no authentication: another browser may select A as well.
    other = TestClient(app)
    lock_url = f"/api/analytics/views/{view_id}/lock"
    locked = other.patch(
        lock_url, json={"locked": True, "revision": 2}, headers=a
    )
    assert locked.status_code == 200
    assert locked.json()["locked"] is True
    assert locked.json()["revision"] == 3
    assert (
        other.patch(
            f"/api/analytics/views/{view_id}",
            json={"name": "ロック中", "config": created["config"], "revision": 3},
            headers=a,
        ).status_code
        == 409
    )
    assert other.delete(f"/api/analytics/views/{view_id}", headers=a).status_code == 409
    assert (
        other.patch(
            lock_url, json={"locked": False, "revision": 2}, headers=a
        ).status_code
        == 409
    )
    assert (
        other.patch(
            lock_url, json={"locked": False, "revision": 3}, headers=b
        ).status_code
        == 404
    )
    unlocked = other.patch(
        lock_url, json={"locked": False, "revision": 3}, headers=a
    )
    assert unlocked.status_code == 200
    assert unlocked.json()["locked"] is False
    assert unlocked.json()["revision"] == 4
    assert (
        other.get("/api/analytics/views", headers=a).json()["views"][0]["name"]
        == "更新"
    )
    assert other.delete(f"/api/analytics/views/{view_id}", headers=a).status_code == 204


def test_character_api_is_public_but_rejects_non_character_writes(client):
    artwork_id = app_db.create_artwork(
        tweet_id="1",
        url="https://example.com/1",
        title="Shared",
        posted_at="2026-10-01T00:00:00+00:00",
    )
    url = f"/api/artworks/{artwork_id}"
    assert client.patch(url, json={"title": "Changed", "likes": 999}).status_code == 422
    response = client.patch(
        url, json={"characters": ["初音ミク", "巡音ルカ", "初音ミク"]}
    )
    assert response.status_code == 200
    assert response.json()["characters"] == ["初音ミク", "巡音ルカ"]
    assert client.patch(url, json={"characters": []}).json()["characters"] == []


def test_metadata_includes_character_usage_counts(client):
    for index, characters in enumerate(
        [["初音ミク", "巡音ルカ"], ["初音ミク"], ["鏡音リン"]]
    ):
        app_db.create_artwork(
            tweet_id=f"metadata-{index}",
            url=f"https://example.com/metadata-{index}",
            title=f"Metadata {index}",
            posted_at="2026-10-01T00:00:00+00:00",
            characters=characters,
        )

    metadata = client.get(
        "/api/analytics/metadata", headers=profile_headers(client)
    ).json()

    assert metadata["character_counts"]["初音ミク"] == 2
    assert metadata["character_counts"]["巡音ルカ"] == 1
    assert metadata["character_counts"]["鏡音リン"] == 1
    assert "初音ミク" in metadata["characters"]


def test_invalid_formulas_and_stages_are_still_rejected(client):
    headers = profile_headers(client)
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


def test_cross_site_writes_are_rejected_without_a_login_flow(client):
    assert (
        client.post(
            "/api/profiles",
            json={"name": "Cross site"},
            headers={"Origin": "https://other.example"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/profiles",
            json={"name": "Same site"},
            headers={"Origin": "http://testserver"},
        ).status_code
        == 201
    )


def test_table_grouping_and_multiple_sorts_round_trip(client):
    headers = profile_headers(client)
    panel = {
        "chart": "table",
        "table_group": "character",
        "table_group_multivalue": "individual",
        "table_group_order": "desc",
        "table_sorts": [
            {"field": "likes", "desc": True},
            {"field": "date", "desc": False},
        ],
        "table_collapsed_groups": ['["character","day","A"]'],
    }
    response = client.post(
        "/api/analytics/views",
        headers=headers,
        json={"name": "Grouped", "config": {"panels": [panel]}},
    )
    assert response.status_code == 201
    saved = client.get("/api/analytics/views", headers=headers).json()["views"][0][
        "config"
    ]["panels"][0]
    for field, value in panel.items():
        assert saved[field] == value
    assert (
        client.post("/api/analytics/query", headers=headers, json=panel).status_code
        == 200
    )


def test_table_grouping_rejects_unknown_fields_and_preserves_legacy_sort(client):
    headers = profile_headers(client)
    for fields in [
        {"table_group": "unknown"},
        {"table_sorts": [{"field": "unknown"}]},
        {"table_sorts": [{"field": "likes"}, {"field": "likes"}]},
        {
            "source": "followers",
            "x": "date",
            "y": ["followers"],
            "columns": ["date"],
            "table_group": "character",
        },
        {"table_sorts": [{"field": "likes"}] * 6},
    ]:
        assert (
            client.post(
                "/api/analytics/query",
                headers=headers,
                json={"chart": "table", **fields},
            ).status_code
            == 422
        )
    for fields in [{"table_sort": "likes", "table_desc": True}, {"table_sorts": []}]:
        assert (
            client.post(
                "/api/analytics/query",
                headers=headers,
                json={"chart": "table", **fields},
            ).status_code
            == 200
        )


def test_scatter_can_be_saved_and_queried_without_login(client):
    headers = profile_headers(client)
    config = {
        "panels": [
            {
                "id": "scatter_1",
                "chart": "scatter",
                "x": "impressions",
                "y": ["likes"],
                "series": "character",
            }
        ]
    }
    response = client.post(
        "/api/analytics/views",
        headers=headers,
        json={"name": "散布図", "config": config},
    )
    assert response.status_code == 201
    views = client.get("/api/analytics/views", headers=headers).json()["views"]
    assert views[0]["config"]["panels"][0]["chart"] == "scatter"
    assert (
        client.post(
            "/api/analytics/query", headers=headers, json=config["panels"][0]
        ).status_code
        == 200
    )
    config["panels"][0]["x"] = "title"
    assert (
        client.post(
            "/api/analytics/query", headers=headers, json=config["panels"][0]
        ).status_code
        == 422
    )


def test_axis_tick_settings_are_saved_and_validate_positive_intervals(client):
    headers = profile_headers(client)
    style = {"x_tick_interval": 6, "y_tick_interval": 25, "x_tick_unit": "hour"}
    created = client.post(
        "/api/analytics/views",
        headers=headers,
        json={
            "name": "目盛り",
            "config": {"panels": [{"x": "measured_at", "style": style}]},
        },
    )
    assert created.status_code == 201
    saved = client.get("/api/analytics/views", headers=headers).json()["views"][0]
    for key, value in style.items():
        assert saved["config"]["panels"][0]["style"][key] == value
    for invalid in [
        {"x_tick_interval": 0},
        {"y_tick_interval": -1},
        {"x_tick_unit": "invalid"},
    ]:
        assert (
            client.post(
                "/api/analytics/query", headers=headers, json={"style": invalid}
            ).status_code
            == 422
        )
    assert (
        client.post(
            "/api/analytics/query",
            headers=headers,
            json={"style": {"x_tick_interval": None, "y_tick_interval": None}},
        ).status_code
        == 200
    )


def test_post_plot_card_uses_requested_stage_and_images(client):
    artwork_id = app_db.create_artwork(
        tweet_id="card",
        url="https://example.com/card",
        title="カード用の投稿",
        posted_at="2026-10-02T00:00:00+00:00",
        image_urls=["https://example.com/art.jpg"],
    )
    for stage, likes, reposts in [("1h", 10, 0), ("24h", 100, 7)]:
        app_db.add_metric_snapshot(
            artwork_id,
            stage=stage,
            elapsed_seconds=3600 if stage == "1h" else 86400,
            measured_at="2026-10-03T00:00:00+00:00",
            likes=likes,
            retweets=reposts,
        )
    headers = profile_headers(client)
    for stage, likes, reposts in [("1h", 10, 0), ("24h", 100, 7)]:
        response = client.post(
            "/api/analytics/query",
            headers=headers,
            json={"chart": "scatter", "x": "likes", "stage": stage},
        )
        assert response.status_code == 200
        artwork = response.json()["points"][0]["artwork"]
        assert artwork["title"] == "カード用の投稿"
        assert artwork["image_urls"] == ["https://example.com/art.jpg"]
        assert (artwork["likes"], artwork["retweets"], artwork["stage"]) == (
            likes,
            reposts,
            stage,
        )


def test_bulk_view_delete_endpoints_preserve_measurements_and_other_profile(client):
    """The UI deletes one view at a time; only view settings may be affected."""
    import sqlite3

    a, b = profile_headers(client), profile_headers(client, 1)
    artwork = app_db.create_artwork(
        tweet_id="reset-integrity", url="https://example.test/reset",
        title="残す作品", posted_at="2026-10-01T23:59:00+09:00",
        image_urls=["https://example.test/image.jpg"], characters=["A"],
    )
    app_db.add_metric_snapshot(
        artwork, stage="24h", elapsed_seconds=86400,
        measured_at="2026-10-02T23:59:00+09:00", likes=42,
    )
    app_db.add_account_metric(123, "2026-10-02T23:59:00+09:00")

    def measurements():
        with sqlite3.connect(app_db.DB_PATH) as connection:
            return {
                table: connection.execute(f"SELECT * FROM {table} ORDER BY rowid").fetchall()
                for table in ["artworks", "artwork_images", "artwork_tags", "metric_snapshots", "account_metrics"]
            }

    before = measurements()
    views = [client.post("/api/analytics/views", headers=a, json={"name":name}).json()
             for name in ["削除1", "削除2", "ロック中"]]
    locked = views[-1]
    assert client.patch(
        f"/api/analytics/views/{locked['id']}/lock", headers=a,
        json={"locked":True, "revision":locked["revision"]},
    ).status_code == 200
    other = client.post("/api/analytics/views", headers=b, json={"name":"別利用者"}).json()
    for view in views[:-1]:
        assert client.delete(f"/api/analytics/views/{view['id']}", headers=a).status_code == 204
    assert client.delete(f"/api/analytics/views/{locked['id']}", headers=a).status_code == 409
    assert client.delete(f"/api/analytics/views/{other['id']}", headers=a).status_code == 404
    remaining = client.get("/api/analytics/views", headers=a).json()["views"]
    assert len(remaining) == 1 and remaining[0]["locked"]
    assert client.get("/api/analytics/views", headers=b).json()["views"] == [other]
    assert measurements() == before
