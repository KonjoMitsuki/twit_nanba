"""Seed a demo analysis profile with sample saved views.

The profile and views are written to app.db (analysis_profiles / analytics_views).
Simple and complex views are included so the analytics UI can be exercised.
Re-running is safe: existing views are skipped unless --update is given.

Usage:
    PYTHONPATH=. python scripts/seed_demo_views.py --dry-run
    PYTHONPATH=. python scripts/seed_demo_views.py
    PYTHONPATH=. python scripts/seed_demo_views.py --db ./app.db --update
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from processing.analysis import query
from processing.analysis_models import Panel, ViewConfig
from storage import app_db

DEFAULT_PROFILE = "デモ"
COLUMNS = ["title", "date", "character", "likes", "retweets", "impressions"]

BASE_PANEL = {
    "title": "パネル",
    "chart": "line",
    "source": "artworks",
    "stage": "24h",
    "x": "character",
    "y": ["likes"],
    "series": "",
    "aggregate": "mean",
    "allocation": "full",
    "period_days": 0,
    "from_date": "",
    "to_date": "",
    "filters": [],
    "filter_join": "and",
    "formulas": [],
    "transform": "none",
    "window": 7,
    "compare_previous": False,
    "bins": 12,
    "show_images": True,
    "columns": COLUMNS,
    "table_sort": "date",
    "table_desc": True,
    "table_sorts": None,
    "table_group": "",
    "table_group_order": "asc",
    "table_group_dates": "day",
    "table_group_multivalue": "individual",
    "table_collapsed_groups": [],
    "style": {},
}

VIEW_SPECS = [
    (
        "デモ：シンプル作品一覧",
        "single",
        [
            {
                "title": "作品一覧（24h時点）",
                "chart": "table",
                "table_sorts": [{"field": "date", "desc": True}],
                "style": {"sort": "x_desc"},
            }
        ],
    ),
    (
        "デモ：キャラ別いいね平均",
        "single",
        [
            {
                "title": "キャラクター別 いいね平均",
                "x": "character",
                "y": ["likes"],
                "aggregate": "mean",
                "style": {
                    "sort": "y_desc",
                    "labels": True,
                    "y_label": "いいね（平均）",
                },
            }
        ],
    ),
    (
        "デモ：フォロワー推移",
        "single",
        [
            {
                "title": "フォロワー数の推移（JST）",
                "source": "followers",
                "x": "date",
                "y": ["followers"],
                "aggregate": "mean",
                "style": {"y_label": "フォロワー数", "x_label": "日付（JST）"},
            }
        ],
    ),
    (
        "デモ：キャラ別の反応構成",
        "single",
        [
            {
                "title": "48hいいねのキャラ別構成",
                "chart": "pie",
                "stage": "48h",
                "x": "character",
                "y": ["likes"],
                "aggregate": "sum",
                "style": {"sort": "y_desc"},
            }
        ],
    ),
    (
        "デモ：複雑ダッシュボード",
        "dashboard",
        [
            {
                "title": "投稿後の伸び（いいね・リポスト）",
                "source": "snapshots",
                "stage": "48h",
                "x": "elapsed_hours",
                "y": ["likes", "retweets"],
                "series": "character",
                "aggregate": "mean",
                "style": {"x_label": "投稿後の経過時間（h）"},
            },
            {
                "title": "24hいいねのばらつき",
                "chart": "box",
                "x": "character",
                "y": ["likes"],
            },
            {
                "title": "24hいいねの分布",
                "chart": "histogram",
                "x": "likes",
                "y": ["likes"],
                "bins": 20,
                "style": {"x_label": "いいね", "y_label": "作品数"},
            },
            {
                "title": "インプレッション×いいね",
                "chart": "scatter",
                "x": "impressions",
                "y": ["likes"],
                "series": "character",
                "style": {"x_label": "インプレッション", "y_label": "いいね"},
            },
            {
                "title": "タグ別インプレッション構成",
                "chart": "pie",
                "x": "tags",
                "y": ["impressions"],
                "aggregate": "sum",
                "style": {"sort": "y_desc"},
            },
        ],
    ),
    (
        "デモ：計算列とフィルター",
        "single",
        [
            {
                "title": "いいね率の高い作品",
                "chart": "table",
                "formulas": [
                    {
                        "key": "calc_like_rate",
                        "label": "いいね率（%）",
                        "expression": "likes / impressions * 100",
                        "scope": "row",
                    },
                    {
                        "key": "calc_reactions",
                        "label": "いいね＋RP",
                        "expression": "likes + retweets",
                        "scope": "row",
                    },
                ],
                "filters": [
                    {
                        "join": "and",
                        "rules": [
                            {"field": "likes", "op": "gte", "value": 100}
                        ],
                    },
                    {
                        "join": "or",
                        "rules": [
                            {"field": "retweets", "op": "gte", "value": 10},
                            {"field": "impressions", "op": "gte", "value": 5000},
                        ],
                    },
                ],
                "columns": [
                    "title",
                    "date",
                    "character",
                    "likes",
                    "retweets",
                    "impressions",
                    "calc_like_rate",
                    "calc_reactions",
                ],
                "table_group": "character",
                "table_sorts": [
                    {"field": "likes", "desc": True},
                    {"field": "date", "desc": True},
                ],
            }
        ],
    ),
    (
        "デモ：前期間比較と移動平均",
        "single",
        [
            {
                "title": "日別いいね（45日・前期間比）",
                "x": "date",
                "y": ["likes"],
                "aggregate": "mean",
                "period_days": 45,
                "compare_previous": True,
                "transform": "moving_average",
                "window": 7,
                "style": {
                    "x_label": "投稿日（JST）",
                    "y_label": "いいね（7点移動平均）",
                },
            }
        ],
    ),
    (
        "デモ：計測ステージの増分",
        "single",
        [
            {
                "title": "計測ごとのいいね増分",
                "source": "snapshots",
                "stage": "48h",
                "x": "elapsed_hours",
                "y": ["likes"],
                "series": "character",
                "aggregate": "mean",
                "transform": "delta",
                "style": {
                    "x_label": "投稿後の経過時間（h）",
                    "y_label": "前回計測からの増分",
                },
            }
        ],
    ),
    (
        "デモ：タグ別パフォーマンス",
        "single",
        [
            {
                "title": "タグ別インプレッション合計",
                "x": "tags",
                "y": ["impressions"],
                "aggregate": "sum",
                "style": {
                    "sort": "y_desc",
                    "x_label": "タグ",
                    "y_label": "インプレッション合計",
                },
            }
        ],
    ),
]


def panel_id(view_name: str, index: int) -> str:
    digest = hashlib.sha1(f"{view_name}:{index}".encode()).hexdigest()[:12]
    return f"panel_{digest}"


def build_views() -> list[tuple[str, ViewConfig]]:
    views = []
    for name, layout, panels in VIEW_SPECS:
        built = []
        for index, overrides in enumerate(panels):
            config = copy.deepcopy(BASE_PANEL)
            config.update(overrides)
            config["id"] = panel_id(name, index)
            built.append(Panel(**config))
        views.append((name, ViewConfig(version=1, layout=layout, panels=built)))
    return views


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=None, help="Path to app.db (defaults to APP_DB_PATH)"
    )
    parser.add_argument(
        "--profile", default=DEFAULT_PROFILE, help="Analysis profile name to create"
    )
    parser.add_argument(
        "--update", action="store_true", help="Overwrite views with the same name"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and report without writing"
    )
    args = parser.parse_args()

    db_path = args.db or app_db.DB_PATH
    app_db.DB_PATH = db_path  # query() reads through the module-level path

    views = build_views()
    report = []
    for name, config in views:
        panels = []
        for panel in config.panels:
            result = query(panel)
            panels.append(
                {
                    "chart": panel.chart,
                    "points": len(result["points"]),
                    "rows": len(result["rows"]),
                    "excluded": result["excluded_count"],
                }
            )
        report.append({"view": name, "panels": panels})

    if args.dry_run:
        print(
            json.dumps(
                {"db": db_path, "dry_run": True, "views": report},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    app_db.init_db(db_path)
    profiles = app_db.list_analysis_profiles(db_path)
    profile = next((item for item in profiles if item["name"] == args.profile), None)
    if profile is None:
        profile = app_db.create_analysis_profile(args.profile, db_path)

    existing = {
        view["name"]: view
        for view in app_db.list_analysis_views(profile["id"], db_path)
    }
    created, updated, skipped = [], [], []
    for name, config in views:
        payload = config.model_dump()
        current = existing.get(name)
        if current is None:
            app_db.create_analysis_view(
                profile["id"], name, payload, db_path
            )
            created.append(name)
        elif args.update:
            app_db.update_analysis_view(
                profile["id"],
                current["id"],
                name,
                payload,
                current["revision"],
                db_path,
            )
            updated.append(name)
        else:
            skipped.append(name)

    print(
        json.dumps(
            {
                "db": db_path,
                "profile": {"id": profile["id"], "name": profile["name"]},
                "created": created,
                "updated": updated,
                "skipped": skipped,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
