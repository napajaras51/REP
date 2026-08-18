import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from nhso_rep_webapp.app.main import create_app
from nhso_rep_webapp.app.services.date_presets import (
    build_date_presets,
    current_fiscal_year_range,
    month_range,
    previous_month_range,
)
from nhso_rep_webapp.app.services.settings_store import SettingsStore


class DatePresetTests(unittest.TestCase):
    def test_month_range_uses_calendar_length(self):
        self.assertEqual(month_range(2024, 2), (date(2024, 2, 1), date(2024, 2, 29)))

    def test_previous_month_crosses_calendar_year(self):
        self.assertEqual(
            previous_month_range(date(2026, 1, 15)),
            (date(2025, 12, 1), date(2025, 12, 31)),
        )

    def test_thai_fiscal_year_starts_in_october(self):
        self.assertEqual(
            current_fiscal_year_range(date(2026, 8, 18)),
            (date(2025, 10, 1), date(2026, 9, 30)),
        )
        self.assertEqual(
            current_fiscal_year_range(date(2026, 10, 1)),
            (date(2026, 10, 1), date(2027, 9, 30)),
        )

    def test_presets_return_iso_dates(self):
        presets = build_date_presets(date(2026, 8, 18))
        self.assertEqual([item["id"] for item in presets], [
            "current_month",
            "previous_month",
            "current_fiscal_year",
        ])
        self.assertEqual(presets[1]["start_date"], "2026-07-01")


class SettingsStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name) / "webapp_settings.json"
        self.store = SettingsStore(self.path, default_destination=r"D:\REP")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_defaults_do_not_create_or_modify_legacy_settings(self):
        settings = self.store.get()
        self.assertEqual(settings["default_destination"], r"D:\REP")
        self.assertFalse(self.path.exists())

    def test_save_is_whitelisted_and_persists(self):
        result = self.store.save(
            {
                "default_destination": r"D:\REP\69",
                "default_page_size": 2000,
                "default_insecure": True,
            }
        )
        raw = json.loads(self.path.read_text(encoding="utf-8"))

        self.assertEqual(result["default_page_size"], 2000)
        self.assertNotIn("token", raw)
        self.assertNotIn("password", raw)
        self.assertFalse(self.path.with_suffix(".json.tmp").exists())

    def test_secret_or_unknown_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            self.store.save({"sso_token": "must-not-save"})

    def test_recent_dates_are_updated_without_changing_destination(self):
        self.store.save({"default_destination": r"D:\REP\69"})
        self.store.update_recent(date(2026, 5, 1), date(2026, 5, 31))
        settings = self.store.get()

        self.assertEqual(settings["default_destination"], r"D:\REP\69")
        self.assertEqual(settings["last_start_date"], "2026-05-01")


class SettingsApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = SettingsStore(
            Path(self.temp_dir.name) / "webapp_settings.json",
            default_destination=r"D:\REP",
        )
        self.client = TestClient(
            create_app(job_manager=MagicMock(), settings_store=self.store)
        )

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def test_settings_get_put_and_page(self):
        initial = self.client.get("/api/settings")
        update = self.client.put(
            "/api/settings",
            json={
                "default_destination": r"D:\REP\69",
                "default_page_size": 1500,
                "default_insecure": True,
                "last_start_date": None,
                "last_end_date": None,
            },
        )
        page = self.client.get("/settings")

        self.assertEqual(initial.status_code, 200)
        self.assertEqual(update.status_code, 200)
        self.assertEqual(update.json()["default_page_size"], 1500)
        self.assertEqual(page.status_code, 200)
        self.assertIn("ค่าเริ่มต้นของ Web App", page.text)

    def test_presets_endpoint_and_validation(self):
        presets = self.client.get("/api/settings/presets")
        invalid = self.client.put(
            "/api/settings",
            json={
                "default_destination": " ",
                "default_page_size": 0,
                "default_insecure": False,
            },
        )

        self.assertEqual(presets.status_code, 200)
        self.assertEqual(len(presets.json()["presets"]), 3)
        self.assertEqual(invalid.status_code, 422)


if __name__ == "__main__":
    unittest.main()
