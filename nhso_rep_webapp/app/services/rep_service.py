"""Safe web-facing adapters around the existing NHSO REP core."""

from pathlib import Path

import requests
import urllib3

import nhso_rep_paginated_download as core


def get_default_destination() -> str:
    """Read only the legacy destination setting needed by the form."""
    try:
        settings = core.load_settings(core.config_path())
    except (OSError, ValueError):
        settings = {}
    return str(settings.get("path") or r"C:\TEMP\REP")


def check_auth_status(insecure: bool = False) -> dict:
    """Refresh the saved SSO session and return sanitized status metadata."""
    session = requests.Session()
    session.verify = not insecure
    if insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    try:
        token_path = core.sso_token_path()
        try:
            token = core.load_sso_token(token_path)
        except RuntimeError:
            return {"status": "login_required", "logged_in": False, "hcode": None}
        if not token:
            return {"status": "login_required", "logged_in": False, "hcode": None}

        try:
            token = core.refresh_token(session, token)
            core.save_sso_token(token_path, token)
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            info = core.auth_info(session, headers, token)
        except requests.RequestException:
            return {"status": "session_expired", "logged_in": False, "hcode": None}

        hospital = (info.get("user") or {}).get("refHospital") or {}
        hcode = str(hospital.get("hmain") or "") or None
        return {"status": "ready", "logged_in": True, "hcode": hcode}
    finally:
        session.close()


def login_sso() -> dict:
    """Open the existing Playwright SSO flow without returning its token."""
    core.browser_sso_login(core.sso_token_path())
    return {"success": True, "status": "ready"}


def run_download(request, *, dry_run: bool) -> dict:
    """Run the shared REP service using validated web request values."""
    return core.download_rep(
        start=request.start_date.isoformat(),
        end=request.end_date.isoformat(),
        dest_path=Path(request.destination),
        hcode=request.hcode,
        overwrite=request.overwrite,
        dry_run=dry_run,
        insecure=request.insecure,
    )
