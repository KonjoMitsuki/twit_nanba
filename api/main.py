"""FastAPI application for X Art Analytics."""

import fcntl
import logging
import time
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
from scraper.auto_detect import check_new_art_post
from scraper.browser import create_browser_context, random_wait
from processing.character_mapper import character_for_tags
from storage import app_db

app = FastAPI(title="X Art Analytics API", version="1.0.0")
logger = logging.getLogger("api")

LOCK_PATH = Path(__file__).resolve().parent.parent / ".process.lock"
_manual_detect_running = False
_last_manual_trigger_ts = 0.0
MANUAL_TRIGGER_COOLDOWN_SEC = 3 * 60


class ArtworkCharacterUpdate(BaseModel):
    character: str | None = Field(default=None, max_length=100)


def _try_acquire_process_lock():
    """cron の main.py と同じロックファイルで排他制御する。"""
    lock_file = open(LOCK_PATH, "w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock_file.close()
        return None
    return lock_file


async def _run_manual_detect(lock_file) -> None:
    global _manual_detect_running
    try:
        async with create_browser_context(headless=True) as (_context, page):
            detected = await check_new_art_post(page, config.X_SCREEN_NAME)
            await random_wait()
            logger.info("手動巡回完了: 新規検知=%s", detected)
    except Exception as error:
        logger.error("手動巡回エラー: %s", error)
    finally:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        lock_file.close()
        _manual_detect_running = False


@app.on_event("startup")
def startup() -> None:
    app_db.init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/detect/trigger")
def trigger_detect(background_tasks: BackgroundTasks):
    global _manual_detect_running, _last_manual_trigger_ts
    now = time.time()

    if _manual_detect_running:
        raise HTTPException(status_code=409, detail="すでに巡回中です")

    if now - _last_manual_trigger_ts < MANUAL_TRIGGER_COOLDOWN_SEC:
        remain = int(MANUAL_TRIGGER_COOLDOWN_SEC - (now - _last_manual_trigger_ts))
        raise HTTPException(
            status_code=429,
            detail=f"{remain}秒後にもう一度お試しください",
        )

    lock_file = _try_acquire_process_lock()
    if lock_file is None:
        raise HTTPException(
            status_code=409,
            detail="定期処理(cron)が実行中です。しばらくお待ちください",
        )

    _manual_detect_running = True
    _last_manual_trigger_ts = now
    background_tasks.add_task(_run_manual_detect, lock_file)
    return {"status": "started"}


@app.get("/api/detect/status")
def detect_status():
    return {"running": _manual_detect_running}


@app.get("/api/calendar")
def calendar(year: int = Query(..., ge=2000, le=2200), month: int = Query(..., ge=1, le=12)):
    result = app_db.get_calendar(year, month)
    screen_name = config.X_SCREEN_NAME.lstrip("@").strip()
    result["tracked_profile_url"] = f"https://x.com/{screen_name}" if screen_name else None
    return result


@app.get("/api/artworks/{artwork_id}")
def artwork(artwork_id: str):
    result = app_db.get_artwork(artwork_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    screen_name = config.X_SCREEN_NAME.lstrip("@").strip()
    result["tracked_profile_url"] = f"https://x.com/{screen_name}" if screen_name else None
    return result


@app.get("/api/artworks/{artwork_id}/metrics")
def metrics(artwork_id: str):
    if app_db.get_artwork(artwork_id) is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return {"artwork_id": artwork_id, "points": app_db.get_metrics(artwork_id)}


@app.patch("/api/artworks/{artwork_id}")
def update_artwork_character(artwork_id: str, payload: ArtworkCharacterUpdate):
    artwork = app_db.get_artwork(artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    app_db.update_artwork(
        artwork_id,
        character=payload.character or "",
    )
    return app_db.get_artwork(artwork_id)


@app.post("/api/artworks/{artwork_id}/character/auto")
def auto_fill_artwork_character(artwork_id: str):
    artwork = app_db.get_artwork(artwork_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    if artwork.get("character"):
        return artwork
    character = character_for_tags(artwork.get("tags", []), config.CHARACTER_MAP_PATH)
    if character:
        app_db.update_artwork(artwork_id, character=character)
    return app_db.get_artwork(artwork_id)


@app.get("/api/followers")
def followers(from_date: str = Query(..., alias="from"), to_date: str = Query(..., alias="to")):
    return {"points": app_db.get_followers(from_date, to_date)}


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@app.get("/artworks/{artwork_id}")
def artwork_page(artwork_id: str):
    if app_db.get_artwork(artwork_id) is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return FileResponse(WEB_DIR / "detail.html")


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
