"""Credential-free web settings and date preset routes."""

from fastapi import APIRouter, HTTPException, Request

from ..models.schemas import WebSettings
from ..services.date_presets import build_date_presets


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=WebSettings)
def get_settings(request: Request):
    try:
        return request.app.state.settings_store.get()
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail="Web settings are unavailable") from exc


@router.put("", response_model=WebSettings)
def update_settings(settings: WebSettings, request: Request):
    try:
        return request.app.state.settings_store.save(settings.model_dump(mode="json"))
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="Web settings could not be saved") from exc


@router.get("/presets")
def date_presets():
    return {"presets": build_date_presets()}
