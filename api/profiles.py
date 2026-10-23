"""Public named profiles: settings separation without authentication."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from storage import app_db

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileName(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)


def selected_profile(request: Request):
    profile_id = request.headers.get("X-Analysis-Profile", "")
    profile = app_db.get_analysis_profile(profile_id)
    if profile is None:
        raise HTTPException(400, "利用者を選択してください")
    return profile


@router.get("")
def profiles():
    return {"profiles": app_db.list_analysis_profiles()}


@router.post("", status_code=201)
def add_profile(payload: ProfileName):
    return app_db.create_analysis_profile(payload.name)


@router.patch("/{profile_id}")
def rename_profile(profile_id: str, payload: ProfileName):
    try:
        return app_db.rename_analysis_profile(profile_id, payload.name)
    except KeyError as error:
        raise HTTPException(404, "利用者が見つかりません") from error
    except app_db.ViewConflict as error:
        raise HTTPException(409, str(error)) from error


async def same_origin_writes(request: Request, call_next):
    # This is not authentication: anyone can choose any profile.
    if request.url.path.startswith("/api/"):
        origin = request.headers.get("origin")
        if request.method not in {"GET", "HEAD", "OPTIONS"} and origin:
            expected = f"{request.url.scheme}://{request.url.netloc}"
            if origin != expected:
                return JSONResponse(
                    {"detail": "同じサイトから操作してください"}, status_code=403
                )
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response
