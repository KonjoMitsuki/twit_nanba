"""Backfill app.db account metrics from historical metric snapshots.

Usage:
    PYTHONPATH=. python scripts/backfill_account_metrics.py --db ./app.db --dry-run
    PYTHONPATH=. python scripts/backfill_account_metrics.py --db ./app.db
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import app_db


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="Path to app.db (defaults to APP_DB_PATH)")
    parser.add_argument("--dry-run", action="store_true", help="Only report planned changes")
    args = parser.parse_args()
    result = app_db.backfill_account_metrics_from_snapshots(
        args.db,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()