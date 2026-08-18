"""Background download job status and log routes."""

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}")
def job_status(job_id: str, request: Request):
    job = request.app.state.job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job


@router.get("/{job_id}/logs")
def job_logs(job_id: str, request: Request):
    logs = request.app.state.job_manager.get_logs(job_id)
    if logs is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return {"job_id": job_id, "logs": logs}
