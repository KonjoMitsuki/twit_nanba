import sqlite3
from datetime import date

import pytest

from processing.analysis import evaluate, parse_formula, query
from processing.analysis_models import Panel
from processing.character_mapper import characters_for_tags
from storage import app_db


@pytest.fixture
def dataset(tmp_path, monkeypatch):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "analysis.db"))
    ids = []
    for index, (characters, likes) in enumerate(
        [(["A", "B"], 100), (["A"], 200), (["B"], None)]
    ):
        artwork_id = app_db.create_artwork(
            tweet_id=str(index),
            url=f"https://example.com/{index}",
            title=f"Art {index}",
            posted_at="2026-10-01T15:00:00+00:00",
            characters=characters,
        )
        ids.append(artwork_id)
        if likes is not None:
            app_db.add_metric_snapshot(
                artwork_id,
                stage="24h",
                elapsed_seconds=86400,
                measured_at="2026-10-02T15:00:00+00:00",
                likes=likes,
                impressions=1000,
            )
        app_db.add_metric_snapshot(
            artwork_id,
            stage="1h",
            elapsed_seconds=3600,
            measured_at="2026-10-01T16:00:00+00:00",
            likes=20,
            impressions=100,
        )
    return ids


def test_missing_stage_is_not_substituted_and_jst_is_explicit(dataset):
    result = query(Panel(chart="table", from_date="2026-10-02", to_date="2026-10-02"))
    assert len(result["rows"]) == 3
    assert result["missing_stage_count"] == 1
    missing = next(row for row in result["rows"] if not row["snapshot_id"])
    assert missing["likes"] is None
    plot = query(Panel(aggregate="sum"))
    assert plot["excluded_count"] == 1
    assert {p["x"]: p["y"] for p in plot["points"]} == {"A": 300, "B": 100}


def test_multicharacter_allocation_and_weighted_mean(dataset):
    split = query(Panel(aggregate="sum", allocation="split"))
    assert {p["x"]: p["y"] for p in split["points"]} == {"A": 250, "B": 50}
    mean = query(Panel(aggregate="mean", allocation="split"))
    assert next(p["y"] for p in mean["points"] if p["x"] == "A") == pytest.approx(
        250 / 1.5
    )
    combinations = query(Panel(aggregate="sum", allocation="combination"))
    assert {p["x"] for p in combinations["points"]} == {"A", "A + B"}


def test_formula_row_vs_group_and_invalid_arithmetic(dataset):
    formula = {
        "key": "calc_rate",
        "label": "Rate",
        "expression": "likes / impressions * 100",
    }
    result = query(Panel(y=["calc_rate"], formulas=[formula]))
    assert next(p["y"] for p in result["points"] if p["x"] == "A") == 15
    formula.update(scope="group", expression="sum(likes) / sum(impressions) * 100")
    result = query(Panel(y=["calc_rate"], formulas=[formula]))
    assert next(p["y"] for p in result["points"] if p["x"] == "A") == 15
    assert (
        evaluate(
            parse_formula("likes / impressions", {"likes", "impressions"}),
            {"likes": 10, "impressions": 0},
        )
        is None
    )


def test_group_formulas_respect_fractional_weights_and_report_invalid_results(dataset):
    formula = {
        "key": "calc_weighted",
        "label": "Weighted mean",
        "expression": "mean(likes)",
        "scope": "group",
    }
    result = query(Panel(y=["calc_weighted"], formulas=[formula], allocation="split"))
    assert next(p["y"] for p in result["points"] if p["x"] == "A") == pytest.approx(
        250 / 1.5
    )
    formula["expression"] = "sum(likes) / 0"
    result = query(Panel(y=["calc_weighted"], formulas=[formula]))
    assert result["points"] == []
    assert result["excluded_count"] == 3


@pytest.mark.parametrize(
    "expression",
    [
        "__import__('os')",
        "likes.real",
        "[likes]",
        "(x for x in likes)",
        "open(1)",
        "10 ** 10000000",
    ],
)
def test_formula_cannot_execute_code_or_unbounded_power(expression):
    try:
        tree = parse_formula(expression, {"likes"})
    except ValueError:
        return
    assert evaluate(tree, {"likes": 10}) is None


def test_box_histogram_and_filters(dataset):
    box = query(Panel(chart="box"))
    a = next(p for p in box["points"] if p["x"] == "A")
    assert (a["q1"], a["median"], a["q3"]) == (125, 150, 175)
    histogram = query(Panel(chart="histogram", x="likes", bins=5))
    assert sum(p["y"] for p in histogram["points"]) == 2
    filtered = query(
        Panel(
            filters=[
                {
                    "join": "or",
                    "rules": [
                        {"field": "likes", "op": "gte", "value": 150},
                        {"field": "title", "op": "eq", "value": "never"},
                    ],
                }
            ]
        )
    )
    assert filtered["artwork_count"] == 1
    assert filtered["points"][0]["y"] == 200


def test_followers_are_independent_and_source_fields_are_checked(dataset):
    app_db.add_account_metric(100, "2026-10-01T15:00:00+00:00")
    app_db.add_account_metric(120, "2026-10-02T15:00:00+00:00")
    result = query(
        Panel(source="followers", x="date", y=["followers"], transform="delta")
    )
    assert [p["y"] for p in result["points"]] == [None, 20]
    with pytest.raises(ValueError):
        query(Panel(source="followers", x="character", y=["likes"]))


def test_previous_period_alignment():
    rows = [
        {"id": str(i), "row_id": str(i), "date": day, "followers": value}
        for i, (day, value) in enumerate(
            [
                ("2026-10-01", 100),
                ("2026-10-02", 120),
                ("2026-10-03", 150),
                ("2026-10-04", 170),
            ]
        )
    ]
    result = query(
        Panel(
            source="followers",
            x="date",
            y=["followers"],
            period_days=2,
            compare_previous=True,
        ),
        now=date(2026, 10, 4),
        rows=rows,
    )
    assert {p["x"] for p in result["points"]} == {"2026-10-03", "2026-10-04"}
    assert {p["series"] for p in result["points"]} == {"前期間", "現在"}


def test_manual_characters_survive_collector_and_explicit_clear(dataset):
    artwork_id = dataset[0]
    app_db.update_artwork(
        artwork_id, characters=["手動", "選択"], character_manual=True
    )
    app_db.upsert_artwork(
        tweet_id="0",
        url="https://example.com/0",
        title="Updated",
        posted_at="2026-10-01T15:00:00+00:00",
        characters=["自動"],
    )
    assert app_db.get_artwork(artwork_id)["characters"] == ["手動", "選択"]
    app_db.update_artwork(artwork_id, characters=[], character_manual=True)
    app_db.auto_fill_characters(artwork_id, ["自動"])
    assert app_db.get_artwork(artwork_id)["characters"] == []


def test_multicharacter_mapping_legacy_migration_and_idempotency(tmp_path):
    path = tmp_path / "map.csv"
    path.write_text("tag,character\nMiku,初音ミク\nLuka,巡音ルカ\n", encoding="utf-8")
    assert characters_for_tags([" #MIKU ", "luka", "Miku"], path) == [
        "初音ミク",
        "巡音ルカ",
    ]
    db = str(tmp_path / "legacy.db")
    artwork_id = app_db.create_artwork(
        tweet_id="1",
        url="https://example.com/1",
        title="Legacy",
        posted_at="2026-10-01T00:00:00+00:00",
        character="初音ミク",
        db_path=db,
    )
    with sqlite3.connect(db) as connection:
        connection.execute("DROP TABLE artwork_characters")
        connection.execute("ALTER TABLE artworks DROP COLUMN character_manual")
    app_db.init_db(db)
    app_db.init_db(db)
    assert app_db.get_artwork(artwork_id, db)["characters"] == ["初音ミク"]
    app_db.update_artwork(artwork_id, characters=[], character_manual=True, db_path=db)
    app_db.init_db(db)
    assert app_db.get_artwork(artwork_id, db)["characters"] == []


def test_views_are_private_and_revision_conflicts_preserve_changes(dataset):
    view = app_db.create_analysis_view("user_a", "Private", {"version": 1})
    assert app_db.list_analysis_views("user_b") == []
    with pytest.raises(KeyError):
        app_db.update_analysis_view("user_b", view["id"], "Stolen", {}, 1)
    app_db.update_analysis_view("user_a", view["id"], "Updated", {"version": 1}, 1)
    with pytest.raises(app_db.ViewConflict):
        app_db.update_analysis_view("user_a", view["id"], "Stale", {}, 1)
    assert app_db.list_analysis_views("user_a")[0]["name"] == "Updated"
    assert not app_db.delete_analysis_view("user_b", view["id"])


def test_table_photos_are_ordered_and_present_without_the_selected_stage(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(app_db, "DB_PATH", str(tmp_path / "photos.db"))
    urls = ["https://images.example/cover.jpg", "https://images.example/second.jpg"]
    artwork_id = app_db.create_artwork(
        tweet_id="photos",
        url="https://example.com/photos",
        title="写真で識別",
        posted_at="2026-10-01T00:00:00+00:00",
        image_urls=urls,
    )
    app_db.create_artwork(
        tweet_id="no-photos",
        url="https://example.com/no-photos",
        title="画像なし",
        posted_at="2026-10-01T00:00:00+00:00",
    )
    app_db.add_metric_snapshot(
        artwork_id,
        stage="1h",
        elapsed_seconds=3600,
        measured_at="2026-10-01T01:00:00+00:00",
        likes=10,
    )
    rows = query(Panel(chart="table", stage="24h"))["rows"]
    with_photos = next(row for row in rows if row["artwork_id"] == artwork_id)
    assert with_photos["image_urls"] == urls
    assert with_photos["likes"] is None
    assert (
        next(row for row in rows if row["artwork_id"] != artwork_id)["image_urls"] == []
    )
    snapshots = query(Panel(chart="table", source="snapshots"))["rows"]
    assert snapshots[0]["image_urls"] == urls
    assert Panel(chart="table").show_images is True
