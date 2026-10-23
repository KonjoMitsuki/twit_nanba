"""Profile-separated analysis views and read-only analysis queries."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator

import config
from api.profiles import selected_profile
from processing.analysis import available_fields, query, validate_panel
from processing.analysis_demo import CHARACTERS, demo_rows
from processing.analysis_models import Panel, StrictModel, ViewCreate, ViewUpdate
from processing.character_mapper import load_character_map
from storage import app_db

router = APIRouter(
    prefix="/api/analytics",
    dependencies=[Depends(selected_profile)],
    tags=["analytics"],
)
demo_router = APIRouter(prefix="/demo-api", tags=["synthetic demo"])


class DemoQuery(StrictModel):
    panel: Panel
    characters: dict[str, list[str]] = Field(default_factory=dict, max_length=32)

    @field_validator("characters")
    @classmethod
    def bounded_names(cls, value):
        if any(
            len(key) > 60
            or len(names) > 30
            or any(not name.strip() or len(name) > 100 for name in names)
            for key, names in value.items()
        ):
            raise ValueError("デモのキャラクター名を確認してください")
        return value


@demo_router.get("/metadata")
def demo_metadata():
    return {
        "sources": {
            source: [
                {"key": key, "label": label, "type": kind}
                for key, (label, kind) in available_fields(source).items()
            ]
            for source in ["artworks", "snapshots", "followers"]
        },
        "stages": [
            {"name": stage["name"], "seconds": stage["offset_sec"]}
            for stage in config.SCHEDULE_STAGES
        ],
        "characters": CHARACTERS,
    }


@demo_router.post("/query")
def demo_query(payload: DemoQuery):
    try:
        validate_panel(payload.panel)
        return query(
            payload.panel,
            rows=demo_rows(
                payload.panel.source, payload.panel.stage, payload.characters
            ),
        )
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


def validate_config(payload):
    try:
        for panel in payload.config.panels:
            validate_panel(panel)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/metadata")
def metadata():
    return {
        "sources": {
            source: [
                {"key": key, "label": label, "type": kind}
                for key, (label, kind) in available_fields(source).items()
            ]
            for source in ["artworks", "snapshots", "followers"]
        },
        "stages": [
            {"name": stage["name"], "seconds": stage["offset_sec"]}
            for stage in config.SCHEDULE_STAGES
        ],
        "characters": sorted(
            set(app_db.character_names())
            | set(load_character_map(config.CHARACTER_MAP_PATH).values())
        ),
    }


@router.post("/query")
def run_query(panel: Panel):
    try:
        return query(panel)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error


@router.get("/views")
def views(request: Request):
    return {"views": app_db.list_analysis_views(selected_profile(request)["id"])}


@router.post("/views", status_code=201)
def create_view(payload: ViewCreate, request: Request):
    validate_config(payload)
    return app_db.create_analysis_view(
        selected_profile(request)["id"], payload.name, payload.config.model_dump()
    )


@router.patch("/views/{view_id}")
def update_view(view_id: str, payload: ViewUpdate, request: Request):
    validate_config(payload)
    try:
        return app_db.update_analysis_view(
            selected_profile(request)["id"],
            view_id,
            payload.name,
            payload.config.model_dump(),
            payload.revision,
        )
    except KeyError as error:
        raise HTTPException(404, "ビューが見つかりません") from error
    except app_db.ViewConflict as error:
        raise HTTPException(409, str(error)) from error


@router.delete("/views/{view_id}", status_code=204)
def delete_view(view_id: str, request: Request):
    if not app_db.delete_analysis_view(selected_profile(request)["id"], view_id):
        raise HTTPException(404, "ビューが見つかりません")
