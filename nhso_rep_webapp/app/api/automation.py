"""Manual-only, opt-in automation endpoints."""

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import DownloadRequest, PreviousMonthAutomationRequest
from ..services.date_presets import previous_month_range
from ..services.job_manager import JobConflictError


router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/status")
def automation_status():
    return {
        "mode": "manual_only",
        "scheduler_enabled": False,
        "default_dry_run": True,
        "overwrite": False,
    }


@router.post("/previous-month", status_code=status.HTTP_202_ACCEPTED)
def run_previous_month(
    automation: PreviousMonthAutomationRequest,
    request: Request,
):
    settings = request.app.state.settings_store.get()
    start_date, end_date = previous_month_range()
    download_request = DownloadRequest(
        start_date=start_date,
        end_date=end_date,
        destination=automation.destination or settings["default_destination"],
        overwrite=False,
        insecure=(
            settings["default_insecure"]
            if automation.insecure is None
            else automation.insecure
        ),
        hcode=automation.hcode,
        page_size=automation.page_size or settings["default_page_size"],
    )
    try:
        job_id = request.app.state.job_manager.submit(
            download_request,
            dry_run=automation.dry_run,
        )
    except JobConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail="มีงานดาวน์โหลด NHSO กำลังทำงานอยู่",
        ) from exc
    return {
        "job_id": job_id,
        "status": "queued",
        "dry_run": automation.dry_run,
        "overwrite": False,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    }
