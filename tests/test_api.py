import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

import run_webapp
from nhso_rep_webapp.app.main import create_app


class HealthApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = TestClient(self.app)

    def tearDown(self):
        self.client.close()

    def test_health_returns_ok(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_application_metadata_is_stable(self):
        self.assertEqual(self.app.title, "NHSO REP Download Manager")
        self.assertEqual(self.app.version, "0.2.0")


class LocalBindingTests(unittest.TestCase):
    def test_launcher_binds_to_loopback_only(self):
        with patch.object(run_webapp.uvicorn, "run") as run:
            run_webapp.main()

        run.assert_called_once_with(
            "nhso_rep_webapp.app.main:app",
            host="127.0.0.1",
            port=8000,
            reload=False,
        )


if __name__ == "__main__":
    unittest.main()
