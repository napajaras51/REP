import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import nhso_rep_paginated_download as downloader


class AuthenticationRegressionTests(unittest.TestCase):
    def test_missing_sso_session_has_actionable_error_and_closes_session(self):
        session = MagicMock()
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(downloader.requests, "Session", return_value=session),
                patch.object(downloader, "load_sso_token", return_value=None),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "No NHSO SSO session is saved.*--sso-login"
                ):
                    downloader.download_rep(
                        start="2026-05-01",
                        end="2026-05-01",
                        dest_path=temp_dir,
                        config=Path(temp_dir) / "missing-settings.json",
                    )

        session.close.assert_called_once_with()

    def test_expired_sso_session_has_actionable_error_and_closes_session(self):
        session = MagicMock()
        refresh_error = requests.HTTPError("401 Client Error")
        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch.object(downloader.requests, "Session", return_value=session),
                patch.object(downloader, "load_sso_token", return_value="saved-token"),
                patch.object(downloader, "refresh_token", side_effect=refresh_error),
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "Saved NHSO SSO session has expired.*--sso-login"
                ):
                    downloader.download_rep(
                        start="2026-05-01",
                        end="2026-05-01",
                        dest_path=temp_dir,
                        config=Path(temp_dir) / "missing-settings.json",
                    )

        session.close.assert_called_once_with()


class PaginationRegressionTests(unittest.TestCase):
    def test_dry_run_preserves_pagination_and_reports_matched_count(self):
        session = MagicMock()
        pages = [
            (
                [
                    {"filename": "A_25690501.ecd", "loaded": "Y"},
                    {"filename": "OLD_25690430.ecd", "loaded": "Y"},
                ],
                {"totalSize": 3},
            ),
            (
                [{"filename": "B_25690501.ecd", "dataStatus": "1"}],
                {"totalSize": 3},
            ),
        ]
        progress_events = []

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
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
                patch.object(downloader, "search_page", side_effect=pages) as search,
                patch.object(downloader, "download_file") as download_file,
                patch.object(downloader.time, "sleep"),
            ):
                result = downloader.download_rep(
                    start="2026-05-01",
                    end="2026-05-01",
                    dest_path=temp_dir,
                    page_size=2,
                    dry_run=True,
                    config=Path(temp_dir) / "missing-settings.json",
                    progress_callback=progress_events.append,
                )

        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args_list[0].args[3:], (0, 2))
        self.assertEqual(search.call_args_list[1].args[3:], (1, 2))
        download_file.assert_not_called()
        self.assertEqual(result["stats"]["pages"], 2)
        self.assertEqual(result["stats"]["seen"], 3)
        self.assertEqual(result["stats"]["matched"], 2)
        self.assertEqual(result["stats"]["date_skipped"], 1)
        self.assertEqual(result["stats"]["downloaded"], 0)
        self.assertEqual(len(result["files"]), 2)
        self.assertEqual(
            [event["event"] for event in progress_events],
            ["page_loaded", "file_result", "page_loaded", "file_result"],
        )


class OverwriteRegressionTests(unittest.TestCase):
    def test_explicit_overwrite_is_forwarded_without_real_file_write(self):
        session = MagicMock()
        item = {"filename": "A_25690501.ecd", "loaded": "Y"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
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
                    return_value=([item], {"totalSize": 1}),
                ),
                patch.object(
                    downloader,
                    "download_file",
                    return_value=("downloaded", "A_25690501_REP.xls"),
                ) as download_file,
            ):
                result = downloader.download_rep(
                    start="2026-05-01",
                    end="2026-05-01",
                    dest_path=temp_dir,
                    overwrite=True,
                    config=Path(temp_dir) / "missing-settings.json",
                )

        self.assertTrue(download_file.call_args.args[6])
        self.assertTrue(result["overwrite"])
        self.assertEqual(result["stats"]["downloaded"], 1)


if __name__ == "__main__":
    unittest.main()
