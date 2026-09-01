"""SQLite persistence for Notion data backup (history-append only)."""

import sqlite3
from datetime import datetime, timezone


CREATE_ARTWORKS_BACKUP_TABLE = """
CREATE TABLE IF NOT EXISTS artworks_backup (
    page_id        TEXT,
    title          TEXT,
    url            TEXT,
    posted_at      TEXT,
    status         TEXT,
    new_fans_count INTEGER,
    backup_at      TEXT
)
"""

CREATE_METRICS_BACKUP_TABLE = """
CREATE TABLE IF NOT EXISTS metrics_backup (
    snapshot_id      TEXT,
    artwork_page_id  TEXT,
    stage            TEXT,
    impressions      INTEGER,
    likes            INTEGER,
    retweets         INTEGER,
    followers        INTEGER,
    new_fans_count   INTEGER,
    measured_at      TEXT,
    backup_at        TEXT
)
"""


def init_db(db_path: str) -> None:
    """Create backup tables if they do not exist."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_ARTWORKS_BACKUP_TABLE)
        conn.execute(CREATE_METRICS_BACKUP_TABLE)


def backup_artwork(artwork_data: dict, db_path: str) -> None:
    """Append an artwork snapshot to the artworks_backup table."""
    init_db(db_path)
    backup_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO artworks_backup
                (page_id, title, url, posted_at, status, new_fans_count, backup_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artwork_data.get("page_id"),
                artwork_data.get("title"),
                artwork_data.get("url"),
                artwork_data.get("posted_at"),
                artwork_data.get("status"),
                artwork_data.get("new_fans_count", 0),
                backup_at,
            ),
        )


def backup_metrics(metrics_data: dict, db_path: str) -> None:
    """Append a metrics snapshot to the metrics_backup table."""
    init_db(db_path)
    backup_at = datetime.now(timezone.utc).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO metrics_backup
                (snapshot_id, artwork_page_id, stage,
                 impressions, likes, retweets, followers,
                 new_fans_count, measured_at, backup_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics_data.get("snapshot_id"),
                metrics_data.get("artwork_page_id"),
                metrics_data.get("stage"),
                metrics_data.get("impressions", 0),
                metrics_data.get("likes", 0),
                metrics_data.get("retweets", 0),
                metrics_data.get("followers", 0),
                metrics_data.get("new_fans_count", 0),
                metrics_data.get("measured_at"),
                backup_at,
            ),
        )
