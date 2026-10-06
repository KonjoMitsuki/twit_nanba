# AGENTS.md — twit_nanba

Repository-wide instructions for coding agents, including OpenAI Codex and GitHub Copilot.

## Project overview

`twit_nanba` is a personal X (Twitter) artwork analytics and automation system. It detects image posts, tracks engagement and followers, collects selected reaction users, persists data to Notion and SQLite, exposes analytics through FastAPI, serves a vanilla HTML/CSS/JavaScript UI, and supports scheduled X posts.

Data collection reliability, historical data integrity, scheduling, and idempotency are core requirements. This is not only a Web UI project.

## Current stack

- Python 3.12
- FastAPI
- SQLite
- Playwright
- Notion API
- Vanilla HTML / CSS / JavaScript
- pytest

Do not migrate the frontend to React, Next.js, Tailwind, shadcn, or another framework unless explicitly requested. Preserve the current UI direction unless a redesign is requested.

## Important paths

- `main.py`: collector/scheduler entry point
- `config.py`: central configuration and schedule definitions
- `api/main.py`: FastAPI application and Web/API routes
- `storage/app_db.py`: primary SQLite DB for Web UI and analytics
- `storage/fans_db.py`: known/reacting users
- `storage/backup_db.py`: local backup DB
- `scraper/auto_detect.py`: new-art detection and follower collection scheduling
- `scraper/metrics.py`: post metric collection
- `scraper/fans.py`: reaction-user collection
- `scraper/profile.py`: profile/follower extraction
- `scraper/poster.py`: X posting automation
- `processing/scheduler.py`: artwork tracking stages
- `processing/new_fans.py`: new-reactor detection
- `processing/character_mapper.py`: tag-to-character mapping
- `notion_client_wrapper/`: Notion integrations
- `scripts/`: migration/backfill utilities
- `web/`: current frontend
- `tests/`: pytest suite

## Source-of-truth priority

When sources disagree, use this order:

1. current executable code and tests;
2. current configuration;
3. current README;
4. documents under `docs/`;
5. historical assumptions/comments.

Report meaningful code/documentation discrepancies instead of silently following stale documentation.

## Data stores

### app.db

Primary local application DB. Its schema is managed by `storage/app_db.py`. Main tables include `artworks`, `artwork_images`, `artwork_tags`, `metric_snapshots`, and `account_metrics`.

`APP_DB_PATH` can override its location. Preserve compatibility with existing DBs. Prefer additive/idempotent migrations. Never silently delete or rewrite historical analytics.

### fans.db

Stores known/reacting X users for new-reactor detection. Its path is controlled by `FANS_DB_PATH`. Do not confuse it with `app.db`.

### backup.db

Local artwork/metric backup. Do not repurpose it as the primary application DB.

### Notion

Notion remains part of the collector architecture. Do not remove it merely because the Web UI reads `app.db`. A migration away from Notion is an explicit architecture change.

## Artwork metric collection

Tracking stages are defined in `config.py` and are the source of truth. Current stages begin at 5m, 15m, 30m, 1h and continue hourly through 48h. The 1h and 48h stages collect reaction users in addition to numeric metrics.

When changing collection logic:

- preserve existing snapshots and stage ordering;
- avoid duplicate logical snapshots;
- preserve timezone-aware timestamps;
- do not increase X request frequency unnecessarily;
- handle partial failure between Notion and local SQLite writes;
- do not duplicate schedule definitions outside `config.py`.

## Follower collection

Account follower history belongs in `app.db -> account_metrics`, separate from artwork metrics. It must be collectible even when there are no due artworks.

Collection slots come from `config.FOLLOWER_COLLECTION_TIMES`, currently 12:00 and 23:59 JST. Never hard-code these times elsewhere. Attempt/success state is persisted in `.daily_follower_collect`.

When modifying this path, test:

- no-artwork operation;
- each intended slot is logically stored once;
- retry behavior after failure;
- previous-day retry behavior;
- JST midnight/date boundaries;
- chronological querying of `account_metrics`.

Inspect `scraper/auto_detect.py`, `main.py`, and `storage/app_db.py` together for follower-collection changes.

## X access and concurrency

X automation is rate-sensitive. Current profile checks intentionally use 15–30 minute gating plus configured fixed checks. Prefer reusing an existing browser session.

Do not add aggressive polling, unnecessary reloads, or parallel sessions without a clear requirement. Do not remove waits/rate controls merely for performance.

Collector execution and manual detection share `.process.lock` via `fcntl.flock`. Preserve cross-process locking, release locks on exceptions, and avoid competing Playwright sessions on the same account.

Never test real posting against the user's X account just to validate code.

## FastAPI

Keep handlers in `api/main.py` thin. Put DB/query logic in `storage/app_db.py`. Preserve API compatibility with the current vanilla frontend unless the task explicitly coordinates API and UI changes.

Use appropriate HTTP status codes and add/update `TestClient` coverage where practical.

Local server:

```bash
APP_DB_PATH=./app.db PYTHONPATH=. python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## Web UI

The frontend is intentionally vanilla HTML/CSS/JS. Preserve the existing visual identity, artwork prominence, responsive behavior, keyboard/touch interactions, multi-image support, and metric chart usability.

For detail-chart changes verify Likes, Retweets, Impressions, absolute/delta modes, stage/time x-axis behavior, tooltips, and mobile touch interaction.

Use `ui-ux-pro-max` when useful, but repository rules override generic design advice.

## Character/tag handling

Character mapping uses `data/character_map.csv` or `CHARACTER_MAP_PATH`. Auto-fill must not overwrite a manually selected character unless explicitly requested. Keep tag normalization consistent across registration, migration, auto-detection, and Web editing.

## Scheduled posts

Relevant code: `notion_client_wrapper/schedule_queue.py`, `scraper/poster.py`, and `main.py`. Current states include SCHEDULED, PREPARING, POSTED, FAILED.

Preserve duplicate-post prevention, failure reporting, scheduled timestamps, and the concurrency role of PREPARING. Successful tracked-account posts should enter artwork tracking.

## Timezones

The project mixes UTC durable timestamps with JST scheduling/calendar semantics.

- use timezone-aware datetimes;
- use UTC where existing durable measurements do;
- use `Asia/Tokyo` for daily scheduling/calendar semantics;
- never compare naive and aware datetimes;
- test JST midnight boundaries when modifying daily aggregation or follower collection.

## Security

Never commit or expose `.env`, `auth_state.json`, `app.db`, `fans.db`, `backup.db`, DB backups, tokens, cookies, or session data. Preserve `.gitignore` protections.

## Tests and validation

Use pytest. Start with the smallest relevant test file, then broaden.

```bash
PYTHONPATH=. python -m pytest tests/test_app_db.py -q
PYTHONPATH=. python -m pytest tests/test_api.py -q
PYTHONPATH=. python -m pytest -q
```

Tests must not use production DBs, mutate production Notion, post to real X, or depend on real authentication. Use `tmp_path`, monkeypatching, mocks, and fakes.

For DB changes test empty creation, compatibility where relevant, idempotency, duplicate handling, and time boundaries. For collector changes test success and failure paths.

## Data integrity rules

1. Never delete/rewrite historical metrics as an unrelated side effect.
2. Prefer idempotent imports and backfills.
3. Preserve unique tweet/artwork identity.
4. Do not convert missing metrics to zero unless zero is semantically correct.
5. Distinguish account follower history from per-artwork follower values.
6. Keep migrations repeatable where practical.
7. Use dry-run for broad backfills where practical.
8. Make JST aggregation boundaries explicit.

Do not automatically run production migrations/backfills.

## Deployment awareness

A local checkout may differ from the running server. Before deployment work, identify the actual deployment checkout, venv/Python, process manager, and cron configuration. Distinguish the Web/API process from collector scheduling. Do not alter production process-manager/systemd/cron configuration as part of unrelated work.

## Agent working style

Trace the complete affected flow for cross-cutting changes, e.g. X profile -> scraper -> collector -> SQLite/Notion -> FastAPI -> Web UI.

Prefer focused changes. Avoid speculative abstractions and unnecessary dependencies. If a requested change exposes a safe-to-fix bug in the same execution path, fix it with a regression test; report unrelated bugs separately.

Repository-local skills may exist under `.agents/skills/`. Particularly relevant skills include `fastapi`, `sqlite-best-practices`, `python-testing-patterns`, `python-performance-optimization`, `data-analysis`, and `ui-ux-pro-max`. Use them only when relevant; this file takes precedence over generic skill guidance.

## Definition of done

A change is complete when requested behavior is implemented, unrelated behavior is preserved, relevant tests pass, new behavior is tested where practical, external-service actions are mocked in automated tests, DB compatibility/data integrity were considered, UI changes are checked at relevant sizes, no secrets/local DBs are committed, and user-facing/setup/schema/operational docs are updated when behavior changed.

Report any validation that could not be performed and why.
