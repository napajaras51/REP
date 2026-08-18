import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import run_webapp
from nhso_rep_webapp.app.logging_setup import configure_logging
from nhso_rep_webapp.app.main import create_app


class BrowserLauncherTests(unittest.TestCase):
    def test_browser_opens_after_health_is_ready(self):
        response = MagicMock(status=200)
        context = MagicMock()
        context.__enter__.return_value = response
        opener = MagicMock()
        with patch.object(run_webapp, "urlopen", return_value=context) as urlopen:
            opened = run_webapp.open_browser_when_ready(
                url="http://127.0.0.1:8000",
                timeout_seconds=1,
                opener=opener,
            )

        self.assertTrue(opened)
        urlopen.assert_called_once_with("http://127.0.0.1:8000/api/health", timeout=1)
        opener.assert_called_once_with("http://127.0.0.1:8000")

    def test_default_launcher_starts_browser_thread(self):
        thread = MagicMock()
        with (
            patch.object(run_webapp, "configure_logging"),
            patch.object(run_webapp.threading, "Thread", return_value=thread) as thread_type,
            patch.object(run_webapp.uvicorn, "run"),
        ):
            run_webapp.main([])

        self.assertTrue(thread_type.call_args.kwargs["daemon"])
        thread.start.assert_called_once_with()

    def test_windows_launcher_keeps_local_python_entrypoint(self):
        launcher = Path(__file__).resolve().parents[1] / "Start NHSO REP Web App.cmd"
        content = launcher.read_text(encoding="utf-8")

        self.assertIn("run_webapp.py", content)
        self.assertNotIn("0.0.0.0", content)
        self.assertNotIn("shell=True", content)


class LocalAssetTests(unittest.TestCase):
    def test_vendor_assets_are_served_locally(self):
        with TestClient(create_app(job_manager=MagicMock())) as client:
            page = client.get("/")
            bootstrap = client.get("/static/vendor/bootstrap/bootstrap.min.css")
            lucide = client.get("/static/vendor/lucide/lucide.min.js")

        self.assertEqual(page.status_code, 200)
        self.assertNotIn("cdn.jsdelivr.net", page.text)
        self.assertGreater(len(bootstrap.content), 200_000)
        self.assertGreater(len(lucide.content), 300_000)


class LoggingTests(unittest.TestCase):
    def test_rotating_log_path_is_created(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "logs" / "webapp.log"
            root = logging.getLogger()
            previous_handlers = set(root.handlers)
            try:
                configured = configure_logging(path)
                self.assertEqual(configured, path)
                self.assertTrue(path.parent.exists())
            finally:
                for handler in set(root.handlers) - previous_handlers:
                    root.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
