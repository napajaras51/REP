"""Preview and synchronous download routes for the Phase 4 MVP."""

import requests
from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import DownloadRequest
from ..services import rep_service
from ..services.job_manager import JobConflictError


router = APIRouter(prefix="/api/downloads", tags=["downloads"])


def _run_request(request: DownloadRequest, *, dry_run: bool) -> dict:
    try:
        return rep_service.run_download(request, dry_run=dry_run)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        message = str(exc)
        if "SSO" in message or "session" in message.lower():
            raise HTTPException(
                status_code=401,
                detail="NHSO session is not ready. Login again.",
            ) from exc
        raise HTTPException(
            status_code=502,
            detail="NHSO request could not be completed",
        ) from exc
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail="Unable to connect to NHSO") from exc
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Cannot use destination folder") from exc


def _remember_dates(request: Request, download_request: DownloadRequest) -> None:
    try:
        request.app.state.settings_store.update_recent(
            download_request.start_date,
            download_request.end_date,
        )
    except RuntimeError:
        pass


@router.post("/preview")
def preview_download(download_request: DownloadRequest, request: Request):
    _remember_dates(request, download_request)
    return _run_request(download_request, dry_run=True)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def start_download(download_request: DownloadRequest, request: Request):
    _remember_dates(request, download_request)
    try:
        job_id = request.app.state.job_manager.submit(download_request)
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="An NHSO download job is already running",
        ) from exc
    return {"job_id": job_id, "status": "queued"}
