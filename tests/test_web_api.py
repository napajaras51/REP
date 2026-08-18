import unittest
from unittest.mock import MagicMock, patch

import requests
from fastapi.testclient import TestClient

from nhso_rep_webapp.app.main import create_app
from nhso_rep_webapp.app.services.job_manager import JobConflictError


VALID_REQUEST = {
    "start_date": "2026-05-01",
    "end_date": "2026-05-31",
    "destination": r"D:\REP\69\6906",
    "overwrite": False,
    "insecure": False,
    "hcode": None,
}

SERVICE_RESULT = {
    "success": True,
    "status": "completed",
    "hcode": "11066",
    "start_date": "2026-05-01",
    "end_date": "2026-05-31",
    "destination": r"D:\REP\69\6906",
    "dry_run": True,
    "overwrite": False,
    "stats": {
        "pages": 1,
        "seen": 1,
        "matched": 1,
        "date_skipped": 0,
        "status_skipped": 0,
        "exists": 0,
        "downloaded": 0,
        "failed": 0,
    },
    "files": [
        {
            "source_name": "A_25690501.ecd",
            "output_name": "A_25690501_REP.xls",
            "result": "matched",
        }
    ],
    "warnings": [],
    "errors": [],
}


class WebApiTests(unittest.TestCase):
    def setUp(self):
        self.job_manager = MagicMock()
        self.client = TestClient(create_app(job_manager=self.job_manager))

    def tearDown(self):
        self.client.close()

    @patch(
        "nhso_rep_webapp.app.api.pages.get_default_destination",
        return_value=r"D:\REP\69\6906",
    )
    def test_homepage_renders_thai_download_workspace(self, _destination):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("รับชุดข้อมูลผลการตรวจสอบ (REP)", response.text)
        self.assertIn(r"D:\REP\69\6906", response.text)
        self.assertIn("/static/css/app.css", response.text)
        self.assertNotIn("sso_token", response.text.lower())

    @patch("nhso_rep_webapp.app.api.auth.rep_service.check_auth_status")
    def test_auth_status_returns_only_sanitized_metadata(self, check_status):
        check_status.return_value = {
            "status": "ready",
            "logged_in": True,
            "hcode": "11066",
        }
        response = self.client.get("/api/auth/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ready", "logged_in": True, "hcode": "11066"},
        )
        self.assertNotIn("token", response.text.lower())

    @patch("nhso_rep_webapp.app.api.auth.rep_service.login_sso")
    def test_login_uses_service_without_returning_token(self, login):
        login.return_value = {"success": True, "status": "ready"}
        response = self.client.post("/api/auth/login")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "status": "ready"})
        self.assertNotIn("token", response.text.lower())

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_preview_calls_shared_service_as_dry_run(self, run_download):
        run_download.return_value = SERVICE_RESULT
        response = self.client.post("/api/downloads/preview", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["stats"]["matched"], 1)
        self.assertTrue(run_download.call_args.kwargs["dry_run"])
        request = run_download.call_args.args[0]
        self.assertEqual(request.destination, VALID_REQUEST["destination"])
        self.assertFalse(request.overwrite)

    def test_download_queues_background_job(self):
        self.job_manager.submit.return_value = "job-123"
        request_body = dict(VALID_REQUEST, overwrite=True)
        response = self.client.post("/api/downloads", json=request_body)

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json(), {"job_id": "job-123", "status": "queued"})
        self.assertTrue(self.job_manager.submit.call_args.args[0].overwrite)

    def test_second_active_download_is_rejected(self):
        self.job_manager.submit.side_effect = JobConflictError("active")
        response = self.client.post("/api/downloads", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            response.json(),
            {"detail": "An NHSO download job is already running"},
        )

    def test_job_status_and_logs_use_job_manager(self):
        self.job_manager.get.return_value = {"job_id": "job-123", "status": "running"}
        self.job_manager.get_logs.return_value = [
            {"timestamp": "2026-08-18T00:00:00+00:00", "level": "info", "message": "started"}
        ]

        status_response = self.client.get("/api/jobs/job-123")
        logs_response = self.client.get("/api/jobs/job-123/logs")

        self.assertEqual(status_response.status_code, 200)
        self.assertEqual(status_response.json()["status"], "running")
        self.assertEqual(logs_response.status_code, 200)
        self.assertEqual(logs_response.json()["logs"][0]["message"], "started")

    def test_unknown_job_returns_not_found(self):
        self.job_manager.get.return_value = None
        response = self.client.get("/api/jobs/missing")

        self.assertEqual(response.status_code, 404)

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_invalid_date_range_is_rejected_before_service(self, run_download):
        request_body = dict(
            VALID_REQUEST,
            start_date="2026-06-01",
            end_date="2026-05-01",
        )
        response = self.client.post("/api/downloads/preview", json=request_body)

        self.assertEqual(response.status_code, 422)
        run_download.assert_not_called()

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_cross_origin_write_is_blocked_before_service(self, run_download):
        response = self.client.post(
            "/api/downloads/preview",
            json=VALID_REQUEST,
            headers={"Origin": "https://untrusted.example"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"detail": "Cross-origin request blocked"})
        run_download.assert_not_called()

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_expired_session_maps_to_unauthorized(self, run_download):
        run_download.side_effect = RuntimeError("Saved NHSO SSO session has expired")
        response = self.client.post("/api/downloads/preview", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "NHSO session is not ready. Login again."},
        )

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_upstream_runtime_detail_is_not_exposed(self, run_download):
        run_download.side_effect = RuntimeError("sensitive upstream response body")
        response = self.client.post("/api/downloads/preview", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(
            response.json(),
            {"detail": "NHSO request could not be completed"},
        )
        self.assertNotIn("sensitive", response.text)

    @patch("nhso_rep_webapp.app.api.downloads.rep_service.run_download")
    def test_network_failure_is_sanitized(self, run_download):
        run_download.side_effect = requests.ConnectionError("sensitive request detail")
        response = self.client.post("/api/downloads/preview", json=VALID_REQUEST)

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"detail": "Unable to connect to NHSO"})
        self.assertNotIn("sensitive", response.text)


if __name__ == "__main__":
    unittest.main()
