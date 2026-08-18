"""Server-rendered web pages."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.templating import Jinja2Templates

from ..services.rep_service import get_default_destination


templates = Jinja2Templates(directory=Path(__file__).resolve().parents[1] / "templates")
router = APIRouter(include_in_schema=False)


@router.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"default_destination": get_default_destination()},
    )


@router.get("/history")
def history_page(request: Request):
    store = request.app.state.history_store
    jobs = store.list_jobs(limit=200) if store else []
    return templates.TemplateResponse(
        request=request,
        name="history.html",
        context={"jobs": jobs},
    )


@router.get("/jobs/{job_id}")
def job_detail_page(job_id: str, request: Request):
    store = request.app.state.history_store
    job = store.get_job(job_id) if store else None
    if job is None:
        raise HTTPException(status_code=404, detail="Download history not found")
    return templates.TemplateResponse(
        request=request,
        name="job_detail.html",
        context={"job": job},
    )
