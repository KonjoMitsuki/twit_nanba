"""FastAPI application for X Art Analytics."""

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from storage import app_db

app = FastAPI(title="X Art Analytics API", version="1.0.0")


@app.on_event("startup")
def startup() -> None:
    app_db.init_db()


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/calendar")
def calendar(year: int = Query(..., ge=2000, le=2200), month: int = Query(..., ge=1, le=12)):
    return app_db.get_calendar(year, month)


@app.get("/api/artworks/{artwork_id}")
def artwork(artwork_id: str):
    result = app_db.get_artwork(artwork_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return result


@app.get("/api/artworks/{artwork_id}/metrics")
def metrics(artwork_id: str):
    if app_db.get_artwork(artwork_id) is None:
        raise HTTPException(status_code=404, detail="Artwork not found")
    return {"artwork_id": artwork_id, "points": app_db.get_metrics(artwork_id)}


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
