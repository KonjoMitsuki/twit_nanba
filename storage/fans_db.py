"""SQLite persistence for the known fan registry."""

import sqlite3
from datetime import datetime


CREATE_KNOWN_FANS_TABLE = """
CREATE TABLE IF NOT EXISTS known_fans (
    screen_name TEXT PRIMARY KEY,
    first_seen_at TEXT NOT NULL,
    first_tweet_id TEXT
)
"""


def init_db(db_path: str = "fans.db") -> None:
    """Create the local fan registry if it does not exist."""
    with sqlite3.connect(db_path) as connection:
        connection.execute(CREATE_KNOWN_FANS_TABLE)


def get_all_known_users(db_path: str = "fans.db") -> set[str]:
    """Return all known screen names."""
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT screen_name FROM known_fans"
        ).fetchall()
    return {row[0] for row in rows}


def register_new_fans(
    new_fans: set[str],
    first_seen_at: datetime,
    tweet_id: str | None,
    db_path: str = "fans.db",
) -> int:
    """Insert new fans in one transaction and return the inserted count."""
    if not new_fans:
        return 0

    init_db(db_path)
    values = [
        (screen_name, first_seen_at.isoformat(), tweet_id)
        for screen_name in new_fans
    ]
    with sqlite3.connect(db_path) as connection:
        before = connection.total_changes
        connection.executemany(
            """
            INSERT OR IGNORE INTO known_fans
                (screen_name, first_seen_at, first_tweet_id)
            VALUES (?, ?, ?)
            """,
            values,
        )
        return connection.total_changes - before