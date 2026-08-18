import io
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import nhso_rep_paginated_download as downloader


class PureFunctionTests(unittest.TestCase):
    def test_allowed_date_tokens_uses_buddhist_year(self):
        self.assertEqual(
            downloader.allowed_date_tokens("2026-05-01", "2026-05-01"),
            {"25690501"},
        )

    def test_output_name_supports_lower_and_upper_case_extensions(self):
        self.assertEqual(downloader.output_name("ABC.ecd"), "ABC_REP.xls")
        self.assertEqual(downloader.output_name("ABC.ECD"), "ABC_REP.xls")

    def test_ready_status_supports_both_nhso_fields(self):
        self.assertTrue(downloader.is_ready({"loaded": "Y"}))
        self.assertTrue(downloader.is_ready({"dataStatus": "1"}))
        self.assertFalse(downloader.is_ready({"loaded": "N", "dataStatus": "0"}))


class ValidationTests(unittest.TestCase):
    def validate(self, **overrides):
        request = {
            "start": "2026-05-01",
            "end": "2026-05-31",
            "dest_path": r"D:\REP\69\6906",
            "page_size": 3000,
            "hcode": "11066",
        }
        request.update(overrides)
        return downloader.validate_download_request(**request)

    def test_valid_request_is_normalized(self):
        result = self.validate()
        self.assertEqual(result["start"], "2026-05-01")
        self.assertEqual(result["end"], "2026-05-31")
        self.assertEqual(result["destination"], Path(r"D:\REP\69\6906"))

    def test_blank_end_defaults_to_today(self):
        result = self.validate(end="")
        self.assertEqual(result["end"], datetime.now().strftime("%Y-%m-%d"))

    def test_invalid_start_date_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Start date"):
            self.validate(start="01/05/2026")

    def test_reversed_range_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "must not be after"):
            self.validate(start="2026-06-01", end="2026-05-31")

    def test_empty_path_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Destination path"):
            self.validate(dest_path=" ")

    def test_non_positive_page_size_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Page size"):
            self.validate(page_size=0)

    def test_invalid_hospital_code_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Hospital code"):
            self.validate(hcode="ABC")

    def test_legacy_login_requires_credentials(self):
        with self.assertRaisesRegex(ValueError, "username/password"):
            self.validate(legacy_login=True, username="", password="")


class DownloadServiceTests(unittest.TestCase):
    def service_patches(self, items):
        session = MagicMock()
        return (
            session,
            patch.object(downloader.requests, "Session", return_value=session),
            patch.object(downloader, "load_sso_token", return_value="saved-token"),
            patch.object(downloader, "refresh_token", return_value="refreshed-token"),
            patch.object(downloader, "save_sso_token"),
            patch.object(
                downloader,
                "auth_info",
                return_value={
                    "menus": [],
                    "user": {"refHospital": {"hmain": "11066"}},
                },
            ),
            patch.object(
                downloader,
                "search_page",
                return_value=(items, {"totalSize": len(items)}),
            ),
        )

    def run_with_patches(self, items, **options):
        session, *patchers = self.service_patches(items)
        with tempfile.TemporaryDirectory() as temp_dir:
            with patchers[0], patchers[1], patchers[2], patchers[3], patchers[4], patchers[5]:
                result = downloader.download_rep(
                    start="2026-05-01",
                    end="2026-05-01",
                    dest_path=temp_dir,
                    config=Path(temp_dir) / "missing-settings.json",
                    **options,
                )
        session.close.assert_called_once_with()
        return result

    def test_dry_run_returns_structured_matched_result_without_download(self):
        items = [
            {"filename": "READY_25690501.ecd", "loaded": "Y"},
            {"filename": "OLD_25690430.ecd", "loaded": "Y"},
            {"filename": "WAIT_25690501.ecd", "loaded": "N"},
        ]
        with patch.object(downloader, "download_file") as download_file:
            result = self.run_with_patches(items, dry_run=True)

        download_file.assert_not_called()
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "completed")
        self.assertEqual(
            result["stats"],
            {
                "pages": 1,
                "seen": 3,
                "matched": 1,
                "date_skipped": 1,
                "status_skipped": 1,
                "exists": 0,
                "downloaded": 0,
                "failed": 0,
            },
        )
        self.assertEqual(result["files"][0]["result"], "matched")

    def test_download_results_are_classified(self):
        items = [
            {"filename": "A_25690501.ecd", "loaded": "Y"},
            {"filename": "B_25690501.ecd", "loaded": "Y"},
            {"filename": "C_25690501.ecd", "loaded": "Y"},
        ]
        outcomes = [
            ("downloaded", "A_25690501_REP.xls"),
            ("exists", "B_25690501_REP.xls"),
            ("http_500", "C_25690501_REP.xls"),
        ]
        with patch.object(downloader, "download_file", side_effect=outcomes):
            result = self.run_with_patches(items)

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(result["stats"]["matched"], 3)
        self.assertEqual(result["stats"]["downloaded"], 1)
        self.assertEqual(result["stats"]["exists"], 1)
        self.assertEqual(result["stats"]["failed"], 1)
        self.assertEqual(len(result["errors"]), 1)


class DownloadFileTests(unittest.TestCase):
    def test_download_uses_part_file_then_replaces_and_closes_response(self):
        session = MagicMock()
        response = MagicMock(status_code=200, content=b"xls-content")
        session.get.return_value = response
        item = {"filename": "A_25690501.ecd"}

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            result, name = downloader.download_file(
                session,
                {"Authorization": "redacted"},
                "redacted",
                "11066",
                item,
                destination,
                False,
            )
            final_path = destination / name
            part_path = final_path.with_suffix(final_path.suffix + ".part")
            self.assertEqual(final_path.read_bytes(), b"xls-content")
            self.assertFalse(part_path.exists())

        self.assertEqual(result, "downloaded")
        response.close.assert_called_once_with()

    def test_existing_file_is_skipped_without_request(self):
        session = MagicMock()
        item = {"filename": "A_25690501.ecd"}
        with tempfile.TemporaryDirectory() as temp_dir:
            destination = Path(temp_dir)
            (destination / "A_25690501_REP.xls").write_bytes(b"existing")
            result, _ = downloader.download_file(
                session,
                {},
                "redacted",
                "11066",
                item,
                destination,
                False,
            )

        self.assertEqual(result, "exists")
        session.get.assert_not_called()


class CliAdapterTests(unittest.TestCase):
    def test_main_passes_cli_arguments_to_service(self):
        service_result = {
            "stats": {
                "pages": 0,
                "seen": 0,
                "matched": 0,
                "date_skipped": 0,
                "status_skipped": 0,
                "exists": 0,
                "downloaded": 0,
                "failed": 0,
            }
        }
        argv = [
            "--start",
            "2026-05-01",
            "--end",
            "2026-05-31",
            "--path",
            r"D:\REP\69\6906",
            "--dry-run",
            "--insecure",
        ]
        with patch.object(downloader, "download_rep", return_value=service_result) as service:
            with redirect_stdout(io.StringIO()):
                result = downloader.main(argv)

        self.assertIs(result, service_result)
        call = service.call_args.kwargs
        self.assertEqual(call["start"], "2026-05-01")
        self.assertEqual(call["end"], "2026-05-31")
        self.assertEqual(call["dest_path"], r"D:\REP\69\6906")
        self.assertTrue(call["dry_run"])
        self.assertTrue(call["insecure"])


if __name__ == "__main__":
    unittest.main()
