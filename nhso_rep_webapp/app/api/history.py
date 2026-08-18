"""Persisted download history API routes."""

from fastapi import APIRouter, HTTPException, Query, Request


router = APIRouter(prefix="/api/history", tags=["history"])


def _store(request: Request):
    store = request.app.state.history_store
    if store is None:
        raise HTTPException(status_code=503, detail="Download history is unavailable")
    return store


@router.get("")
def list_history(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    return {"jobs": _store(request).list_jobs(limit=limit, offset=offset)}


@router.get("/{job_id}")
def history_detail(job_id: str, request: Request):
    job = _store(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download history not found")
    return job
