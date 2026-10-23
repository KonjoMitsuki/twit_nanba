"""SQLite application database for the web UI."""

from __future__ import annotations

import os
import json
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
    character TEXT,
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
CREATE TABLE IF NOT EXISTS characters (
    name TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS artwork_characters (
    artwork_id TEXT NOT NULL REFERENCES artworks(id) ON DELETE CASCADE,
    character TEXT NOT NULL REFERENCES characters(name),
    PRIMARY KEY (artwork_id, character)
);
CREATE TABLE IF NOT EXISTS analysis_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS analytics_views (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    name TEXT NOT NULL,
    config TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    locked INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_views_owner ON analytics_views(owner, updated_at);

"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path or DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def init_db(db_path: str | None = None) -> None:
    with _connect(db_path) as connection:
        connection.executescript(SCHEMA)
        connection.execute("BEGIN IMMEDIATE")
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(artworks)")
        }
        if "character" not in columns:
            connection.execute("ALTER TABLE artworks ADD COLUMN character TEXT")
        if "character_manual" not in columns:
            connection.execute("ALTER TABLE artworks ADD COLUMN character_manual INTEGER NOT NULL DEFAULT 0")
            connection.execute("UPDATE artworks SET character_manual = 1 WHERE character IS NOT NULL AND TRIM(character) != ''")
            connection.execute("INSERT OR IGNORE INTO characters SELECT DISTINCT TRIM(character) FROM artworks WHERE character IS NOT NULL AND TRIM(character) != ''")
            connection.execute("INSERT OR IGNORE INTO artwork_characters SELECT id, TRIM(character) FROM artworks WHERE character IS NOT NULL AND TRIM(character) != ''")
        view_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(analytics_views)")
        }
        if "locked" not in view_columns:
            connection.execute(
                "ALTER TABLE analytics_views ADD COLUMN locked INTEGER NOT NULL DEFAULT 0"
            )


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
    character: str | None = None,
    characters: list[str] | None = None,
    character_manual: bool = False,
    image_urls: list[str] | None = None,
    tags: list[str] | None = None,
    db_path: str | None = None,
) -> str:
    artwork_id = f"art_{uuid.uuid4().hex[:12]}"
    now = _now()
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            "INSERT INTO artworks (id, tweet_id, url, title, posted_at, status, character, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (artwork_id, tweet_id, url, title, posted_at, status, character, now, now),
        )
        _write_characters(connection, artwork_id, characters if characters is not None else ([character] if character else []), manual=character_manual)
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
    character: str | None = None,
    characters: list[str] | None = None,
    character_manual: bool = False,
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
            "SELECT id FROM artworks WHERE tweet_id = ? OR tweet_id LIKE ? OR url = ? LIMIT 1",
            (tweet_id, f"{tweet_id}?%", url),
        ).fetchone()
        artwork_id = existing["id"] if existing else f"art_{tweet_id}"
        now = _now()
        connection.execute(
            """INSERT INTO artworks
            (id, tweet_id, url, title, posted_at, status, next_schedule,
             character, new_fans_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              tweet_id=excluded.tweet_id, url=excluded.url, title=excluded.title,
              posted_at=excluded.posted_at, status=excluded.status,
              character=CASE WHEN artworks.character_manual = 1 THEN artworks.character ELSE COALESCE(excluded.character, artworks.character) END,
              next_schedule=COALESCE(excluded.next_schedule, artworks.next_schedule),
              new_fans_count=excluded.new_fans_count, updated_at=excluded.updated_at""",
            (artwork_id, tweet_id, url, title, posted_at, status, next_schedule,
             character, new_fans_count, now, now),
        )
        incoming_characters = characters if characters is not None else ([character] if character else None)
        if incoming_characters is not None:
            manual = connection.execute("SELECT character_manual FROM artworks WHERE id = ?", (artwork_id,)).fetchone()[0]
            if character_manual or not manual:
                _write_characters(connection, artwork_id, incoming_characters, manual=character_manual)
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
    character: str | None = None,
    characters: list[str] | None = None,
    character_manual: bool = False,
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
    if character is not None:
        fields["character"] = character.strip() or None
    assignments = ", ".join(f"{key} = ?" for key in fields)
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute(
            f"UPDATE artworks SET {assignments} WHERE id = ?",
            (*fields.values(), artwork_id),
        )
        if characters is not None or character is not None:
            _write_characters(connection, artwork_id, characters if characters is not None else ([character] if character else []), manual=character_manual)


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


def backfill_account_metrics_from_snapshots(
    db_path: str | None = None,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Fill missing account metrics from valid historical snapshots.

    Existing account metrics win when the same timestamp is already present.
    """
    init_db(db_path)
    with _connect(db_path) as connection:
        source_rows = connection.execute(
            """SELECT measured_at, MAX(followers) AS followers
            FROM metric_snapshots
            WHERE followers > 0
            GROUP BY measured_at
            ORDER BY measured_at""",
        ).fetchall()
        existing_times = {
            row[0] for row in connection.execute(
                "SELECT DISTINCT measured_at FROM account_metrics",
            )
        }
        rows_to_insert = [
            (f"account_{uuid.uuid4().hex[:12]}", row["measured_at"], row["followers"])
            for row in source_rows
            if row["measured_at"] not in existing_times
        ]
        if not dry_run and rows_to_insert:
            connection.executemany(
                "INSERT INTO account_metrics (id, measured_at, followers) VALUES (?, ?, ?)",
                rows_to_insert,
            )
    return {
        "source_times": len(source_rows),
        "inserted": len(rows_to_insert),
        "skipped_existing": len(source_rows) - len(rows_to_insert),
    }


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
                "character": item["character"],
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
        artwork["characters"] = [item[0] for item in connection.execute("SELECT character FROM artwork_characters WHERE artwork_id = ? ORDER BY character", (artwork_id,))]
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


def _write_characters(connection, artwork_id, names, *, manual=False):
    names = sorted({name.strip() for name in names if name.strip()})
    connection.executemany("INSERT OR IGNORE INTO characters(name) VALUES (?)", [(name,) for name in names])
    connection.execute("DELETE FROM artwork_characters WHERE artwork_id = ?", (artwork_id,))
    connection.executemany("INSERT INTO artwork_characters VALUES (?, ?)", [(artwork_id, name) for name in names])
    connection.execute(
        "UPDATE artworks SET character = ?, character_manual = ?, updated_at = ? WHERE id = ?",
        (names[0] if names else None, int(manual), _now(), artwork_id),
    )


def character_names(db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        return [row[0] for row in connection.execute("SELECT name FROM characters ORDER BY name")]


def auto_fill_characters(artwork_id, names, db_path=None):
    """Atomically protect manual selections (including an intentional empty set)."""
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT character, character_manual FROM artworks WHERE id = ?", (artwork_id,)).fetchone()
        if row and not row["character_manual"] and not row["character"] and names:
            _write_characters(connection, artwork_id, names)


def auto_fill_missing_characters(resolve, db_path=None, *, dry_run=False):
    """Fill every artwork that has no character yet from its stored tags.

    ``resolve`` receives an artwork's tags and returns the matched characters.
    Manual selections, including an intentional empty set, are never touched,
    and already filled artworks are skipped so repeated scans are idempotent.
    """
    init_db(db_path)
    with _connect(db_path) as connection:
        if not dry_run:
            connection.execute("BEGIN IMMEDIATE")
        scanned = connection.execute("SELECT COUNT(*) FROM artworks").fetchone()[0]
        skipped_manual = connection.execute(
            "SELECT COUNT(*) FROM artworks WHERE character_manual = 1"
        ).fetchone()[0]
        candidates = connection.execute(
            """SELECT a.id, a.title
            FROM artworks a
            WHERE a.character_manual = 0
              AND (a.character IS NULL OR TRIM(a.character) = '')
              AND NOT EXISTS (
                SELECT 1 FROM artwork_characters c WHERE c.artwork_id = a.id
              )
            ORDER BY a.posted_at, a.id"""
        ).fetchall()
        tags_by_artwork: dict[str, list[str]] = {}
        for row in connection.execute(
            "SELECT artwork_id, tag FROM artwork_tags ORDER BY artwork_id, tag"
        ):
            tags_by_artwork.setdefault(row[0], []).append(row[1])
        changes = []
        unmatched = 0
        for row in candidates:
            names = sorted({
                name.strip()
                for name in resolve(tags_by_artwork.get(row["id"], []))
                if name.strip()
            })
            if not names:
                unmatched += 1
                continue
            changes.append({"id": row["id"], "title": row["title"], "characters": names})
            if not dry_run:
                _write_characters(connection, row["id"], names)
    return {
        "dry_run": dry_run,
        "scanned": scanned,
        "skipped_manual": skipped_manual,
        "skipped_existing": scanned - skipped_manual - len(candidates),
        "unmatched": unmatched,
        "filled": 0 if dry_run else len(changes),
        "would_fill": len(changes) if dry_run else 0,
        "changes": changes,
    }


def analysis_rows(source, stage="24h", db_path=None, *, from_date="0001-01-01", to_date="9999-12-31"):
    """Read bounded, independent datasets. Never substitute a missing stage."""
    init_db(db_path)
    with _connect(db_path) as connection:
        if source == "followers":
            rows = [dict(r) for r in connection.execute("SELECT * FROM account_metrics WHERE date(measured_at, '+9 hours') >= ? AND date(measured_at, '+9 hours') <= ? ORDER BY measured_at, id LIMIT 20001", (from_date, to_date))]
            for row in rows:
                row["row_id"] = row["id"]
                row["date"] = datetime.fromisoformat(row["measured_at"]).astimezone(JST).date().isoformat()
        else:
            characters = {}
            for r in connection.execute("SELECT artwork_id, character FROM artwork_characters ORDER BY character"):
                characters.setdefault(r[0], []).append(r[1])
            tags = {}
            for r in connection.execute("SELECT artwork_id, tag FROM artwork_tags ORDER BY tag"):
                tags.setdefault(r[0], []).append(r[1])
            if source == "artworks":
                rows = [dict(r) for r in connection.execute(
                    """SELECT a.*, a.id AS artwork_id, m.id AS snapshot_id,
                    m.stage, m.measured_at, m.elapsed_seconds, m.likes, m.retweets,
                    m.impressions, m.followers, m.new_fans_count AS measured_new_fans
                    FROM artworks a LEFT JOIN metric_snapshots m ON m.id = (
                      SELECT id FROM metric_snapshots WHERE artwork_id = a.id AND stage = ?
                      ORDER BY measured_at DESC, id DESC LIMIT 1)
                    WHERE date(a.posted_at, '+9 hours') >= ? AND date(a.posted_at, '+9 hours') <= ?
                    ORDER BY a.posted_at, a.id LIMIT 20001""", (stage, from_date, to_date))]
            elif source == "snapshots":
                rows = [dict(r) for r in connection.execute(
                    """SELECT a.title, a.url, a.posted_at, a.status, m.*
                    FROM metric_snapshots m JOIN artworks a ON a.id = m.artwork_id
                    WHERE date(a.posted_at, '+9 hours') >= ? AND date(a.posted_at, '+9 hours') <= ?
                    ORDER BY m.artwork_id, m.elapsed_seconds, m.measured_at, m.id LIMIT 20001""", (from_date, to_date))]
            else:
                raise ValueError("不明なデータ種類です")
            images = {}
            for image in connection.execute(
                """SELECT i.artwork_id, i.source_url FROM artwork_images i
                JOIN artworks a ON a.id = i.artwork_id
                WHERE date(a.posted_at, '+9 hours') >= ? AND date(a.posted_at, '+9 hours') <= ?
                ORDER BY i.image_order, i.id""", (from_date, to_date)
            ):
                images.setdefault(image[0], []).append(image[1])
            for row in rows:
                row["row_id"] = row["id"]
                row["image_urls"] = images.get(row["artwork_id"], [])
                row["characters"] = characters.get(row["artwork_id"], [])
                row["tags"] = tags.get(row["artwork_id"], [])
                row["character"] = " + ".join(row["characters"]) or "未設定"
                row["date"] = datetime.fromisoformat(row["posted_at"]).astimezone(JST).date().isoformat()
                row["elapsed_hours"] = row["elapsed_seconds"] / 3600 if row.get("elapsed_seconds") is not None else None
                if "measured_new_fans" in row:
                    row["new_fans_count"] = row.pop("measured_new_fans")
        if len(rows) > 20000:
            raise ValueError("プロトタイプの上限は1回の分析につき20,000行です。期間を絞ってください")
        return rows


class ViewConflict(ValueError):
    pass


class ViewLocked(ValueError):
    pass


def _view_json(row):
    value = dict(row)
    value["config"] = json.loads(value["config"])
    value["locked"] = bool(value.get("locked"))
    value.pop("owner")
    return value


def list_analysis_views(owner, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        return [_view_json(row) for row in connection.execute(
            "SELECT * FROM analytics_views WHERE owner = ? ORDER BY updated_at DESC, id", (owner,))]


def create_analysis_view(owner, name, config, db_path=None):
    init_db(db_path)
    view_id = "view_" + uuid.uuid4().hex
    with _connect(db_path) as connection:
        connection.execute(
            "INSERT INTO analytics_views "
            "(id, owner, name, config, revision, updated_at, locked) "
            "VALUES (?, ?, ?, ?, 1, ?, 0)",
            (
                view_id,
                owner,
                name,
                json.dumps(config, ensure_ascii=False),
                _now(),
            ),
        )
        return _view_json(connection.execute("SELECT * FROM analytics_views WHERE id = ?", (view_id,)).fetchone())


def update_analysis_view(owner, view_id, name, config, revision, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM analytics_views WHERE id = ? AND owner = ?", (view_id, owner)).fetchone()
        if not row:
            raise KeyError(view_id)
        if row["locked"]:
            raise ViewLocked("ロック中のビューは変更できません。先にロックを解除してください")
        if row["revision"] != revision:
            raise ViewConflict("別のタブで更新されています。変更内容を保持したまま再読み込みしてください")
        connection.execute("UPDATE analytics_views SET name = ?, config = ?, revision = revision + 1, updated_at = ? WHERE id = ? AND owner = ?",
                           (name, json.dumps(config, ensure_ascii=False), _now(), view_id, owner))
        return _view_json(connection.execute("SELECT * FROM analytics_views WHERE id = ?", (view_id,)).fetchone())


def set_analysis_view_locked(owner, view_id, locked, revision, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT * FROM analytics_views WHERE id = ? AND owner = ?",
            (view_id, owner),
        ).fetchone()
        if not row:
            raise KeyError(view_id)
        if row["revision"] != revision:
            raise ViewConflict(
                "別のタブで更新されています。再読み込みしてからロックを変更してください"
            )
        connection.execute(
            "UPDATE analytics_views "
            "SET locked = ?, revision = revision + 1, updated_at = ? "
            "WHERE id = ? AND owner = ?",
            (1 if locked else 0, _now(), view_id, owner),
        )
        return _view_json(
            connection.execute(
                "SELECT * FROM analytics_views WHERE id = ?", (view_id,)
            ).fetchone()
        )


def delete_analysis_view(owner, view_id, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT locked FROM analytics_views WHERE id = ? AND owner = ?",
            (view_id, owner),
        ).fetchone()
        if not row:
            return False
        if row["locked"]:
            raise ViewLocked(
                "ロック中のビューは削除できません。先にロックを解除してください"
            )
        return connection.execute(
            "DELETE FROM analytics_views WHERE id = ? AND owner = ?",
            (view_id, owner),
        ).rowcount > 0


def list_analysis_profiles(db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute("SELECT 1 FROM analysis_profiles LIMIT 1").fetchone():
            connection.executemany("INSERT INTO analysis_profiles VALUES (?, ?)",
                                   [("profile_a", "利用者A"), ("profile_b", "利用者B")])
        return [dict(row) for row in connection.execute("SELECT * FROM analysis_profiles ORDER BY rowid")]


def get_analysis_profile(profile_id, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        return _json_row(connection.execute("SELECT * FROM analysis_profiles WHERE id = ?", (profile_id,)).fetchone())


def create_analysis_profile(name, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("INSERT OR IGNORE INTO analysis_profiles VALUES (?, ?)", ("profile_" + uuid.uuid4().hex, name))
        return dict(connection.execute("SELECT * FROM analysis_profiles WHERE name = ?", (name,)).fetchone())


def rename_analysis_profile(profile_id, name, db_path=None):
    init_db(db_path)
    with _connect(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if not connection.execute("SELECT 1 FROM analysis_profiles WHERE id = ?", (profile_id,)).fetchone():
            raise KeyError(profile_id)
        try:
            connection.execute("UPDATE analysis_profiles SET name = ? WHERE id = ?", (name, profile_id))
        except sqlite3.IntegrityError as error:
            raise ViewConflict("同じ名前の利用者がいます。別の名前を入力してください") from error
        return dict(connection.execute("SELECT * FROM analysis_profiles WHERE id = ?", (profile_id,)).fetchone())
