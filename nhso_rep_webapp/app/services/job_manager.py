"""Single-worker in-process job manager for NHSO downloads."""

import copy
import re
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable

from . import rep_service


ACTIVE_STATUSES = {"queued", "running"}
TERMINAL_STATUSES = {"completed", "completed_with_errors", "failed"}
EMPTY_STATS = {
    "pages": 0,
    "seen": 0,
    "matched": 0,
    "date_skipped": 0,
    "status_skipped": 0,
    "exists": 0,
    "downloaded": 0,
    "failed": 0,
}


class JobConflictError(RuntimeError):
    """Raised when a second NHSO job is submitted while one is active."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sanitize_log_message(message: object) -> str:
    """Remove credential-like values before storing a job log message."""
    text = str(message).replace("\r", " ").replace("\n", " ")
    text = re.sub(
        r"(?i)\bauthorization\b\s*[:=]\s*(?:bearer\s+)?[^\s,;]+",
        "Authorization=[redacted]",
        text,
    )
    text = re.sub(
        r"(?i)\b(password|token)\b\s*[:=]\s*[^\s,;]+",
        r"\1=[redacted]",
        text,
    )
    text = re.sub(r"(?i)\bbearer\s+[A-Za-z0-9._~-]+", "Bearer [redacted]", text)
    return text[:2000]


@dataclass
class DownloadJob:
    job_id: str
    request: object
    request_data: dict
    status: str = "queued"
    created_at: str = field(default_factory=utc_now)
    started_at: str | None = None
    completed_at: str | None = None
    progress: dict = field(default_factory=lambda: EMPTY_STATS.copy())
    result: dict | None = None
    error: dict | None = None
    logs: deque = field(default_factory=lambda: deque(maxlen=500))
    history_warning_logged: bool = False


class JobManager:
    """Run at most one NHSO download at a time in a background thread."""

    def __init__(self, runner: Callable | None = None, history_store=None):
        self._runner = runner or rep_service.run_download
        self._history_store = history_store
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="nhso-rep")
        self._jobs: dict[str, DownloadJob] = {}
        self._active_job_id: str | None = None
        self._lock = threading.RLock()

    def submit(self, request) -> str:
        with self._lock:
            if self._active_job_id:
                active = self._jobs.get(self._active_job_id)
                if active and active.status in ACTIVE_STATUSES:
                    raise JobConflictError("An NHSO download job is already running")

            job_id = uuid.uuid4().hex
            request_data = request.model_dump(mode="json")
            job = DownloadJob(job_id=job_id, request=request, request_data=request_data)
            self._jobs[job_id] = job
            self._active_job_id = job_id
            if self._history_store:
                try:
                    self._history_store.create_job(self._snapshot(job))
                except Exception as exc:
                    del self._jobs[job_id]
                    self._active_job_id = None
                    raise RuntimeError("Unable to create download history record") from exc
            self._executor.submit(self._run, job_id)
            return job_id

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return self._snapshot(job) if job else None

    def get_logs(self, job_id: str) -> list[dict] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return copy.deepcopy(list(job.logs)) if job else None

    def shutdown(self, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def _run(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "running"
            job.started_at = utc_now()
            self._append_log(job, "Download job started", "info")
            self._persist(job, "mark_started", self._snapshot(job))

        last_history_update = 0.0

        def progress_callback(event: dict) -> None:
            nonlocal last_history_update
            stats = event.get("stats")
            if not isinstance(stats, dict):
                return
            with self._lock:
                current = self._jobs[job_id]
                current.progress.update(
                    {key: int(stats.get(key, 0)) for key in EMPTY_STATS}
                )
                now = time.monotonic()
                if self._history_store and now - last_history_update >= 0.5:
                    self._persist(current, "update_progress", job_id, current.progress)
                    last_history_update = now

        def log_callback(message: str, level: str = "info") -> None:
            with self._lock:
                self._append_log(self._jobs[job_id], message, level)

        try:
            result = self._runner(
                job.request,
                dry_run=False,
                progress_callback=progress_callback,
                log_callback=log_callback,
            )
            with self._lock:
                current = self._jobs[job_id]
                current.result = result
                current.progress.update(result.get("stats") or {})
                current.status = result.get("status") or "completed"
                if current.status not in TERMINAL_STATUSES:
                    current.status = "completed"
                self._append_log(current, "Download job completed", "info")
        except Exception as exc:
            with self._lock:
                current = self._jobs[job_id]
                message = str(exc)
                auth_error = "SSO" in message or "session" in message.lower()
                current.status = "failed"
                current.error = {
                    "code": "LOGIN_REQUIRED" if auth_error else "JOB_FAILED",
                    "message": (
                        "NHSO session is not ready. Login again."
                        if auth_error
                        else "Download job could not be completed"
                    ),
                }
                self._append_log(current, current.error["message"], "error")
        finally:
            with self._lock:
                current = self._jobs[job_id]
                current.completed_at = utc_now()
                self._persist(current, "complete_job", self._snapshot(current))
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _persist(self, job: DownloadJob, method_name: str, *args) -> None:
        if not self._history_store:
            return
        try:
            getattr(self._history_store, method_name)(*args)
        except Exception:
            if not job.history_warning_logged:
                self._append_log(job, "Download history could not be updated", "warning")
                job.history_warning_logged = True

    def _append_log(self, job: DownloadJob, message: object, level: str) -> None:
        safe_level = level if level in {"debug", "info", "warning", "error"} else "info"
        job.logs.append(
            {
                "timestamp": utc_now(),
                "level": safe_level,
                "message": sanitize_log_message(message),
            }
        )

    @staticmethod
    def _snapshot(job: DownloadJob) -> dict:
        return copy.deepcopy(
            {
                "job_id": job.job_id,
                "status": job.status,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "completed_at": job.completed_at,
                "request": job.request_data,
                "progress": job.progress,
                "result": job.result,
                "error": job.error,
            }
        )
