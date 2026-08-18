"""NHSO authentication status and login routes."""

from fastapi import APIRouter, HTTPException, Query

from ..models.schemas import AuthLoginResponse, AuthStatusResponse
from ..services import rep_service


router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/status", response_model=AuthStatusResponse)
def auth_status(insecure: bool = Query(default=False)):
    try:
        return rep_service.check_auth_status(insecure=insecure)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to access local SSO state") from exc


@router.post("/login", response_model=AuthLoginResponse)
def auth_login():
    try:
        return rep_service.login_sso()
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Unable to save local SSO state") from exc
