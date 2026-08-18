import threading
import time
import unittest
from datetime import date
from unittest.mock import MagicMock

from nhso_rep_webapp.app.models.schemas import DownloadRequest
from nhso_rep_webapp.app.services.job_manager import JobConflictError, JobManager


def request_model():
    return DownloadRequest(
        start_date=date(2026, 5, 1),
        end_date=date(2026, 5, 1),
        destination=r"D:\REP\69\6906",
    )


def wait_for_status(manager, job_id, statuses, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.get(job_id)
        if job and job["status"] in statuses:
            return job
        time.sleep(0.01)
    raise AssertionError(f"Job {job_id} did not reach {statuses}")


class JobManagerTests(unittest.TestCase):
    def test_single_worker_reports_progress_result_and_sanitized_logs(self):
        release = threading.Event()
        progress_sent = threading.Event()

        def runner(_request, *, dry_run, progress_callback, log_callback):
            self.assertFalse(dry_run)
            progress_callback(
                {
                    "event": "file_result",
                    "stats": {
                        "pages": 1,
                        "seen": 2,
                        "matched": 1,
                        "date_skipped": 1,
                        "status_skipped": 0,
                        "exists": 0,
                        "downloaded": 1,
                        "failed": 0,
                    },
                }
            )
            progress_sent.set()
            log_callback("Authorization: Bearer secret-token", level="warning")
            release.wait(timeout=2)
            return {
                "status": "completed",
                "stats": {
                    "pages": 1,
                    "seen": 2,
                    "matched": 1,
                    "date_skipped": 1,
                    "status_skipped": 0,
                    "exists": 0,
                    "downloaded": 1,
                    "failed": 0,
                },
                "files": [],
            }

        manager = JobManager(runner=runner)
        try:
            job_id = manager.submit(request_model())
            running = wait_for_status(manager, job_id, {"running"})
            self.assertTrue(progress_sent.wait(timeout=1))
            running = manager.get(job_id)
            self.assertEqual(running["progress"]["downloaded"], 1)
            with self.assertRaises(JobConflictError):
                manager.submit(request_model())

            release.set()
            completed = wait_for_status(manager, job_id, {"completed"})
            self.assertEqual(completed["result"]["stats"]["matched"], 1)
            logs = manager.get_logs(job_id)
            log_text = " ".join(item["message"] for item in logs)
            self.assertNotIn("secret-token", log_text)
            self.assertIn("[redacted]", log_text)
        finally:
            release.set()
            manager.shutdown(wait=True)

    def test_failure_is_terminal_and_does_not_expose_exception_detail(self):
        def runner(_request, **_kwargs):
            raise RuntimeError("SSO token sensitive-detail session expired")

        manager = JobManager(runner=runner)
        try:
            job_id = manager.submit(request_model())
            failed = wait_for_status(manager, job_id, {"failed"})
            self.assertEqual(failed["error"]["code"], "LOGIN_REQUIRED")
            self.assertNotIn("sensitive-detail", str(failed))
            self.assertIsNotNone(failed["completed_at"])
        finally:
            manager.shutdown(wait=True)

    def test_unknown_job_returns_none(self):
        manager = JobManager(runner=lambda *_args, **_kwargs: {})
        try:
            self.assertIsNone(manager.get("missing"))
            self.assertIsNone(manager.get_logs("missing"))
        finally:
            manager.shutdown(wait=True)

    def test_terminal_job_is_persisted_to_history_store(self):
        history = MagicMock()

        def runner(_request, **_kwargs):
            return {"status": "completed", "stats": {"matched": 0}, "files": []}

        manager = JobManager(runner=runner, history_store=history)
        try:
            job_id = manager.submit(request_model())
            wait_for_status(manager, job_id, {"completed"})
            history.create_job.assert_called_once()
            history.mark_started.assert_called_once()
            history.complete_job.assert_called_once()
        finally:
            manager.shutdown(wait=True)

    def test_dry_run_job_is_forwarded_to_runner_and_request_snapshot(self):
        calls = []

        def runner(_request, *, dry_run, **_kwargs):
            calls.append(dry_run)
            return {"status": "completed", "stats": {}, "files": []}

        manager = JobManager(runner=runner)
        try:
            job_id = manager.submit(request_model(), dry_run=True)
            completed = wait_for_status(manager, job_id, {"completed"})
            self.assertEqual(calls, [True])
            self.assertTrue(completed["request"]["dry_run"])
        finally:
            manager.shutdown(wait=True)


if __name__ == "__main__":
    unittest.main()
