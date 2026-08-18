import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from nhso_rep_webapp.app.services.history_store import HistoryStore, SCHEMA_VERSION


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
            "insecure": True,
        },
        "progress": {},
        "result": None,
        "error": None,
    }


class HistoryStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.store = HistoryStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_schema_is_initialized_without_credential_columns(self):
        with closing(sqlite3.connect(self.db_path)) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]
            schema = " ".join(
                row[0]
                for row in connection.execute(
                    "SELECT sql FROM sqlite_master WHERE type = 'table' AND sql IS NOT NULL"
                )
            ).lower()

        self.assertEqual(version, SCHEMA_VERSION)
        self.assertNotIn("password", schema)
        self.assertNotIn("sso_token", schema)
        self.assertNotIn("authorization", schema)

    def test_job_lifecycle_and_files_are_persisted(self):
        snapshot = queued_snapshot()
        self.store.create_job(snapshot)

        snapshot["status"] = "running"
        snapshot["started_at"] = "2026-08-18T01:00:01+00:00"
        self.store.mark_started(snapshot)
        self.store.update_progress(
            snapshot["job_id"],
            {"pages": 1, "seen": 2, "matched": 1, "downloaded": 1},
        )

        snapshot["status"] = "completed"
        snapshot["completed_at"] = "2026-08-18T01:00:03+00:00"
        snapshot["progress"] = {
            "pages": 1,
            "seen": 2,
            "matched": 1,
            "date_skipped": 1,
            "status_skipped": 0,
            "exists": 0,
            "downloaded": 1,
            "failed": 0,
        }
        snapshot["result"] = {
            "files": [
                {
                    "source_name": "A_25690501.ecd",
                    "output_name": "A_25690501_REP.xls",
                    "result": "downloaded",
                }
            ]
        }
        self.store.complete_job(snapshot)

        jobs = self.store.list_jobs()
        detail = self.store.get_job(snapshot["job_id"])
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "completed")
        self.assertEqual(jobs[0]["stats"]["downloaded"], 1)
        self.assertEqual(detail["files"][0]["result"], "downloaded")
        self.assertFalse(detail["overwrite"])

    def test_history_persists_across_store_instances(self):
        self.store.create_job(queued_snapshot())
        reopened = HistoryStore(self.db_path)

        self.assertEqual(reopened.get_job("job-001")["id"], "job-001")

    def test_limits_are_bounded_and_missing_job_returns_none(self):
        self.assertEqual(self.store.list_jobs(limit=0), [])
        self.assertIsNone(self.store.get_job("missing"))


if __name__ == "__main__":
    unittest.main()
