"""Preview and synchronous download routes for the Phase 4 MVP."""

import requests
from fastapi import APIRouter, HTTPException

from ..models.schemas import DownloadRequest
from ..services import rep_service


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


@router.post("/preview")
def preview_download(request: DownloadRequest):
    return _run_request(request, dry_run=True)


@router.post("")
def start_download(request: DownloadRequest):
    return _run_request(request, dry_run=False)
