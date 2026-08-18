import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from nhso_rep_webapp.app.main import create_app
from nhso_rep_webapp.app.services.history_store import HistoryStore


def queued_snapshot():
    return {
        "job_id": "job-001",
        "status": "queued",
        "created_at": "2026-08-18T01:00:00+00:00",
        "started_at": None,
        "completed_at": None,
        "request": {
            "start_date": "2026-05-01",
            "end_date": "2026-05-31",
            "destination": r"D:\REP\69\6906",
            "hcode": "11066",
            "overwrite": False,
            "insecure": False,
        },
        "progress": {},
        "result": None,
        "error": None,
    }


class HistoryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = HistoryStore(Path(self.temp_dir.name) / "app.db")
        self.store.create_job(queued_snapshot())
        self.client = TestClient(
            create_app(job_manager=MagicMock(), history_store=self.store)
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_history_api_lists_and_returns_detail(self):
        listing = self.client.get("/api/history")
        detail = self.client.get("/api/history/job-001")

        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.json()["jobs"][0]["id"], "job-001")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["destination"], r"D:\REP\69\6906")

    def test_history_pages_render(self):
        listing = self.client.get("/history")
        detail = self.client.get("/jobs/job-001")

        self.assertEqual(listing.status_code, 200)
        self.assertIn("งานดาวน์โหลดที่ผ่านมา", listing.text)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(r"D:\REP\69\6906", detail.text)

    def test_missing_history_returns_not_found(self):
        self.assertEqual(self.client.get("/api/history/missing").status_code, 404)
        self.assertEqual(self.client.get("/jobs/missing").status_code, 404)


if __name__ == "__main__":
    unittest.main()
