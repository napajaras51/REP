import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

from nhso_rep_webapp.app.models.schemas import DownloadRequest
from nhso_rep_webapp.app.services import rep_service


class AuthServiceTests(unittest.TestCase):
    def test_missing_token_returns_login_required_and_closes_session(self):
        session = MagicMock()
        with (
            patch.object(rep_service.requests, "Session", return_value=session),
            patch.object(rep_service.core, "load_sso_token", return_value=None),
        ):
            result = rep_service.check_auth_status()

        self.assertEqual(
            result,
            {"status": "login_required", "logged_in": False, "hcode": None},
        )
        session.close.assert_called_once_with()

    def test_valid_token_is_refreshed_and_returns_only_hcode(self):
        session = MagicMock()
        with (
            patch.object(rep_service.requests, "Session", return_value=session),
            patch.object(rep_service.core, "load_sso_token", return_value="saved-token"),
            patch.object(rep_service.core, "refresh_token", return_value="refreshed-token"),
            patch.object(rep_service.core, "save_sso_token") as save_token,
            patch.object(
                rep_service.core,
                "auth_info",
                return_value={"user": {"refHospital": {"hmain": "11066"}}},
            ),
        ):
            result = rep_service.check_auth_status(insecure=True)

        self.assertEqual(result, {"status": "ready", "logged_in": True, "hcode": "11066"})
        self.assertNotIn("token", result)
        self.assertFalse(session.verify)
        save_token.assert_called_once()
        session.close.assert_called_once_with()

    def test_refresh_failure_returns_expired_without_exception_detail(self):
        session = MagicMock()
        with (
            patch.object(rep_service.requests, "Session", return_value=session),
            patch.object(rep_service.core, "load_sso_token", return_value="saved-token"),
            patch.object(
                rep_service.core,
                "refresh_token",
                side_effect=requests.HTTPError("sensitive request detail"),
            ),
        ):
            result = rep_service.check_auth_status()

        self.assertEqual(
            result,
            {"status": "session_expired", "logged_in": False, "hcode": None},
        )
        self.assertNotIn("sensitive", str(result))
        session.close.assert_called_once_with()

    def test_login_returns_status_without_browser_token(self):
        with patch.object(
            rep_service.core,
            "browser_sso_login",
            return_value="browser-token-must-not-leave-service",
        ) as browser_login:
            result = rep_service.login_sso()

        self.assertEqual(result, {"success": True, "status": "ready"})
        self.assertNotIn("token", result)
        browser_login.assert_called_once()


class DownloadAdapterTests(unittest.TestCase):
    def test_request_is_mapped_to_shared_download_service(self):
        request = DownloadRequest(
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
            destination=r"D:\REP\69\6906",
            overwrite=True,
            insecure=True,
            hcode="11066",
        )
        expected = {"success": True, "stats": {"matched": 0}}
        with patch.object(rep_service.core, "download_rep", return_value=expected) as download:
            result = rep_service.run_download(request, dry_run=True)

        self.assertIs(result, expected)
        download.assert_called_once_with(
            start="2026-05-01",
            end="2026-05-31",
            dest_path=Path(r"D:\REP\69\6906"),
            hcode="11066",
            overwrite=True,
            dry_run=True,
            insecure=True,
            page_size=3000,
            progress_callback=None,
            log_callback=None,
        )

    def test_default_destination_does_not_expose_other_settings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings_path = Path(temp_dir) / "settings.json"
            with (
                patch.object(rep_service.core, "config_path", return_value=settings_path),
                patch.object(
                    rep_service.core,
                    "load_settings",
                    return_value={
                        "path": r"D:\REP\69\6906",
                        "username": "must-not-be-returned",
                        "password": "must-not-be-returned",
                    },
                ),
            ):
                result = rep_service.get_default_destination()

        self.assertEqual(result, r"D:\REP\69\6906")
        self.assertNotIn("must-not-be-returned", result)


if __name__ == "__main__":
    unittest.main()
