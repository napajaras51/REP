import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from nhso_rep_webapp.app.main import create_app
from nhso_rep_webapp.app.services.job_manager import JobConflictError


class AutomationApiTests(unittest.TestCase):
    def setUp(self):
        self.job_manager = MagicMock()
        self.job_manager.submit.return_value = "automation-job"
        self.settings_store = MagicMock()
        self.settings_store.get.return_value = {
            "default_destination": r"D:\REP\69\6906",
            "default_page_size": 3000,
            "default_insecure": True,
            "last_start_date": None,
            "last_end_date": None,
        }
        self.client = TestClient(
            create_app(
                job_manager=self.job_manager,
                settings_store=self.settings_store,
            )
        )

    def tearDown(self):
        self.client.close()

    def test_automation_status_is_manual_and_scheduler_disabled(self):
        response = self.client.get("/api/automation/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "mode": "manual_only",
                "scheduler_enabled": False,
                "default_dry_run": True,
                "overwrite": False,
            },
        )

    @patch(
        "nhso_rep_webapp.app.api.automation.previous_month_range",
        return_value=(date(2026, 7, 1), date(2026, 7, 31)),
    )
    def test_previous_month_defaults_to_dry_run_and_never_overwrites(self, _range):
        response = self.client.post("/api/automation/previous-month", json={})

        self.assertEqual(response.status_code, 202)
        self.assertTrue(response.json()["dry_run"])
        self.assertFalse(response.json()["overwrite"])
        request = self.job_manager.submit.call_args.args[0]
        self.assertEqual(request.start_date, date(2026, 7, 1))
        self.assertEqual(request.end_date, date(2026, 7, 31))
        self.assertEqual(request.destination, r"D:\REP\69\6906")
        self.assertFalse(request.overwrite)
        self.assertTrue(self.job_manager.submit.call_args.kwargs["dry_run"])

    @patch(
        "nhso_rep_webapp.app.api.automation.previous_month_range",
        return_value=(date(2026, 7, 1), date(2026, 7, 31)),
    )
    def test_manual_actual_mode_still_disables_overwrite(self, _range):
        response = self.client.post(
            "/api/automation/previous-month",
            json={"dry_run": False, "destination": r"D:\REP\69\automation"},
        )

        self.assertEqual(response.status_code, 202)
        self.assertFalse(response.json()["dry_run"])
        request = self.job_manager.submit.call_args.args[0]
        self.assertFalse(request.overwrite)
        self.assertFalse(self.job_manager.submit.call_args.kwargs["dry_run"])

    def test_active_job_conflict_is_rejected(self):
        self.job_manager.submit.side_effect = JobConflictError("active")
        response = self.client.post("/api/automation/previous-month", json={})

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "JOB_CONFLICT")

    def test_settings_page_exposes_manual_dry_run_action(self):
        response = self.client.get("/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn("previousMonthDryRun", response.text)
        self.assertIn("ตรวจสอบแบบ Dry Run", response.text)


if __name__ == "__main__":
    unittest.main()
