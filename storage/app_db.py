"""SQLite application database for the web UI."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

DB_PATH = os.getenv("APP_DB_PATH", str(Path(__file__).resolve().parent.parent / "app.db"))
JST = ZoneInfo("Asia/Tokyo")

SCHEMA = """
CREATE TABLE IF NOT EXISTS artworks (
    id TEXT PRIMARY KEY,
    tweet_id TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    posted_at TEXT NOT NULL,
    status TEXT NOT NULL,
    next_schedule TEXT,
    new_fans_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS artwork_images (
    id TEXT PRIMARY KEY,
    artwork_id TEXT NOT NULL,
    image_order INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    storage_key TEXT,
    width INTEGER,
    height INTEGER,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS artwork_tags (
    artwork_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    PRIMARY KEY (artwork_id, tag),
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS metric_snapshots (
    id TEXT PRIMARY KEY,
    artwork_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    elapsed_seconds INTEGER NOT NULL,
    measured_at TEXT NOT NULL,
    impressions INTEGER NOT NULL DEFAULT 0,
    likes INTEGER NOT NULL DEFAULT 0,
    retweets INTEGER NOT NULL DEFAULT 0,
    followers INTEGER,
    new_fans_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (artwork_id) REFERENCES artworks(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_metric_artwork_time ON metric_snapshots(artwork_id, elapsed_seconds);
CREATE TABLE IF NOT EXISTS account_metrics (
    id TEXT PRIMARY KEY,
    measured_at TEXT NOT NULL,
    followers INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_account_metrics_time ON account_metrics(measured_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: str | None = None) -> None:
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)


def _json_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def find_artwork_by_tweet_id(
    tweet_id: str,
    db_path: str | None = None,
) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        return _json_row(connection.execute(
            "SELECT * FROM artworks WHERE tweet_id = ?",
            (tweet_id,),
        ).fetchone())


def metric_exists(
    artwork_id: str,
    stage: str,
    db_path: str | None = None,
) -> bool:
    init_db(db_path)
    with _connect(db_path) as connection:
        return connection.execute(
            "SELECT 1 FROM metric_snapshots WHERE artwork_id = ? AND stage = ?",
            (artwork_id, stage),
        ).fetchone() is not None


def create_artwork(
    *,
    tweet_id: str,
    url: str,
    title: str,
    posted_at: str,
    status: str = "TRACKING",
    image_urls: list[str] | None = None,
    tags: list[str] | None = None,
    db_path: str | None = None,
) -> str:
    artwork_id = f"art_{uuid.uuid4().hex[:12]}"
    now = _now()
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            "INSERT INTO artworks (id, tweet_id, url, title, posted_at, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (artwork_id, tweet_id, url, title, posted_at, status, now, now),
        )
        for order, image_url in enumerate(image_urls or [], 1):
            connection.execute(
                "INSERT INTO artwork_images (id, artwork_id, image_order, source_url) VALUES (?, ?, ?, ?)",
                (f"img_{uuid.uuid4().hex[:12]}", artwork_id, order, image_url),
            )
        for tag in tags or []:
            connection.execute("INSERT OR IGNORE INTO artwork_tags (artwork_id, tag) VALUES (?, ?)", (artwork_id, tag))
    return artwork_id


def upsert_artwork(
    *,
    tweet_id: str,
    url: str,
    title: str,
    posted_at: str,
    status: str = "TRACKING",
    next_schedule: str | None = None,
    new_fans_count: int = 0,
    image_urls: list[str] | None = None,
    tags: list[str] | None = None,
    db_path: str | None = None,
) -> str:
    """Insert or update an artwork using the X post ID as the stable key."""
    init_db(db_path)
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM artworks WHERE tweet_id = ? OR url = ? LIMIT 1",
            (tweet_id, url),
        ).fetchone()
        artwork_id = existing["id"] if existing else f"art_{tweet_id}"
        now = _now()
        connection.execute(
            """INSERT INTO artworks
            (id, tweet_id, url, title, posted_at, status, next_schedule,
             new_fans_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              tweet_id=excluded.tweet_id, url=excluded.url, title=excluded.title,
              posted_at=excluded.posted_at, status=excluded.status,
              next_schedule=excluded.next_schedule,
              next_schedule=COALESCE(excluded.next_schedule, artworks.next_schedule),
              new_fans_count=excluded.new_fans_count, updated_at=excluded.updated_at""",
            (artwork_id, tweet_id, url, title, posted_at, status, next_schedule,
             new_fans_count, now, now),
        )
        if image_urls:
            connection.execute("DELETE FROM artwork_images WHERE artwork_id = ?", (artwork_id,))
            for order, image_url in enumerate(image_urls, 1):
                connection.execute(
                    "INSERT INTO artwork_images (id, artwork_id, image_order, source_url) VALUES (?, ?, ?, ?)",
                    (f"img_{uuid.uuid4().hex[:12]}", artwork_id, order, image_url),
                )
        if tags is not None:
            connection.execute("DELETE FROM artwork_tags WHERE artwork_id = ?", (artwork_id,))
            connection.executemany(
                "INSERT OR IGNORE INTO artwork_tags (artwork_id, tag) VALUES (?, ?)",
                [(artwork_id, tag) for tag in tags],
            )
    return artwork_id


def update_artwork(
    artwork_id: str,
    *,
    status: str | None = None,
    next_schedule: str | None = None,
    new_fans_count: int | None = None,
    db_path: str | None = None,
) -> None:
    """Update the mutable fields written by the collector."""
    fields: dict[str, Any] = {"updated_at": _now()}
    if status is not None:
        fields["status"] = status
    if next_schedule is not None or status == "COMPLETED":
        fields["next_schedule"] = next_schedule
    if new_fans_count is not None:
        fields["new_fans_count"] = new_fans_count
    assignments = ", ".join(f"{key} = ?" for key in fields)
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            f"UPDATE artworks SET {assignments} WHERE id = ?",
            (*fields.values(), artwork_id),
        )


def add_metric_snapshot(
    artwork_id: str,
    *,
    stage: str,
    elapsed_seconds: int,
    measured_at: str,
    impressions: int = 0,
    likes: int = 0,
    retweets: int = 0,
    followers: int | None = None,
    new_fans_count: int = 0,
    db_path: str | None = None,
) -> str:
    init_db(db_path)
    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM metric_snapshots WHERE artwork_id = ? AND stage = ?",
            (artwork_id, stage),
        ).fetchone()
        if existing:
            connection.execute(
                """UPDATE metric_snapshots SET elapsed_seconds=?, measured_at=?,
                impressions=?, likes=?, retweets=?, followers=?, new_fans_count=?
                WHERE id=?""",
                (elapsed_seconds, measured_at, impressions, likes, retweets,
                 followers, new_fans_count, existing["id"]),
            )
            return existing["id"]
        snapshot_id = f"metric_{uuid.uuid4().hex[:12]}"
        connection.execute(
            "INSERT INTO metric_snapshots (id, artwork_id, stage, elapsed_seconds, measured_at, impressions, likes, retweets, followers, new_fans_count) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (snapshot_id, artwork_id, stage, elapsed_seconds, measured_at, impressions, likes, retweets, followers, new_fans_count),
        )
    return snapshot_id


def add_account_metric(followers: int, measured_at: str, db_path: str | None = None) -> str:
    metric_id = f"account_{uuid.uuid4().hex[:12]}"
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("INSERT INTO account_metrics (id, measured_at, followers) VALUES (?, ?, ?)", (metric_id, measured_at, followers))
    return metric_id


def _month_bounds(year: int, month: int) -> tuple[str, str]:
    start_jst = datetime(year, month, 1, tzinfo=JST)
    next_month_jst = datetime(
        year + (month == 12),
        1 if month == 12 else month + 1,
        1,
        tzinfo=JST,
    )
    return start_jst.astimezone(timezone.utc).isoformat(), next_month_jst.astimezone(timezone.utc).isoformat()


def _day_delta(connection: sqlite3.Connection, day: date) -> int | None:
    start = datetime.combine(day, datetime.min.time(), JST).astimezone(timezone.utc).isoformat()
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), JST).astimezone(timezone.utc).isoformat()
    current = connection.execute("SELECT followers FROM account_metrics WHERE measured_at >= ? AND measured_at < ? ORDER BY measured_at DESC LIMIT 1", (start, end)).fetchone()
    prior = connection.execute("SELECT followers FROM account_metrics WHERE measured_at < ? ORDER BY measured_at DESC LIMIT 1", (start,)).fetchone()
    if not current or not prior:
        return None
    return current["followers"] - prior["followers"]


def get_calendar(year: int, month: int, db_path: str | None = None) -> dict[str, Any]:
    start, end = _month_bounds(year, month)
    first_day = date(year, month, 1)
    next_month = first_day + timedelta(days=32)
    last_day = date(next_month.year, next_month.month, 1) - timedelta(days=1)
    init_db(db_path)
    with _connect(db_path) as connection:
        rows = connection.execute(
            """SELECT a.*, (SELECT source_url FROM artwork_images i WHERE i.artwork_id = a.id ORDER BY image_order LIMIT 1) AS image_url,
            (SELECT likes FROM metric_snapshots m WHERE m.artwork_id = a.id ORDER BY elapsed_seconds DESC LIMIT 1) AS likes,
            (SELECT retweets FROM metric_snapshots m WHERE m.artwork_id = a.id ORDER BY elapsed_seconds DESC LIMIT 1) AS retweets,
            (SELECT impressions FROM metric_snapshots m WHERE m.artwork_id = a.id ORDER BY elapsed_seconds DESC LIMIT 1) AS impressions
            FROM artworks a WHERE a.posted_at >= ? AND a.posted_at < ? ORDER BY a.posted_at""",
            (start, end),
        ).fetchall()
        days = {
            (first_day + timedelta(days=offset)).isoformat(): {
                "date": (first_day + timedelta(days=offset)).isoformat(),
                "followers_delta": _day_delta(connection, first_day + timedelta(days=offset)),
                "artworks": [],
            }
            for offset in range(last_day.day)
        }
        for row in rows:
            item = dict(row)
            posted_at = datetime.fromisoformat(item["posted_at"]).astimezone(JST)
            day = posted_at.date().isoformat()
            days[day]["artworks"].append({
                "id": item["id"], "title": item["title"], "posted_at": item["posted_at"], "image_url": item["image_url"],
                "likes": item["likes"], "retweets": item["retweets"], "impressions": item["impressions"], "status": item["status"],
            })
        month_rows = connection.execute(
            """SELECT COALESCE(SUM(likes), 0) AS likes, COALESCE(SUM(retweets), 0) AS retweets
            FROM metric_snapshots m JOIN artworks a ON a.id = m.artwork_id
            WHERE a.posted_at >= ? AND a.posted_at < ? AND m.id IN (SELECT id FROM metric_snapshots GROUP BY artwork_id HAVING elapsed_seconds = MAX(elapsed_seconds))""",
            (start, end),
        ).fetchone()
        latest_account = connection.execute("SELECT followers FROM account_metrics WHERE measured_at < ? ORDER BY measured_at DESC LIMIT 1", (end,)).fetchone()
        first_account = connection.execute("SELECT followers FROM account_metrics WHERE measured_at < ? ORDER BY measured_at DESC LIMIT 1", (start,)).fetchone()
    return {
        "year": year, "month": month,
        "summary": {"followers": latest_account["followers"] if latest_account else None, "followers_delta": (latest_account["followers"] - first_account["followers"]) if latest_account and first_account else None, "posts": len(rows), "likes": month_rows["likes"], "retweets": month_rows["retweets"]},
        "days": list(days.values()),
    }


def get_artwork(artwork_id: str, db_path: str | None = None) -> dict[str, Any] | None:
    init_db(db_path)
    with _connect(db_path) as connection:
        row = connection.execute("SELECT * FROM artworks WHERE id = ?", (artwork_id,)).fetchone()
        if not row:
            return None
        artwork = dict(row)
        artwork["images"] = [dict(item) for item in connection.execute("SELECT * FROM artwork_images WHERE artwork_id = ? ORDER BY image_order", (artwork_id,))]
        artwork["tags"] = [item[0] for item in connection.execute("SELECT tag FROM artwork_tags WHERE artwork_id = ? ORDER BY tag", (artwork_id,))]
        artwork["latest"] = _json_row(connection.execute("SELECT * FROM metric_snapshots WHERE artwork_id = ? ORDER BY elapsed_seconds DESC LIMIT 1", (artwork_id,)).fetchone())
    return artwork


def get_metrics(artwork_id: str, db_path: str | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM metric_snapshots WHERE artwork_id = ? ORDER BY elapsed_seconds", (artwork_id,))]


def get_followers(from_date: str, to_date: str, db_path: str | None = None) -> list[dict[str, Any]]:
    init_db(db_path)
    with _connect(db_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM account_metrics WHERE measured_at >= ? AND measured_at < ? ORDER BY measured_at", (from_date, to_date))]
