import argparse
import base64
import ctypes
import json
import logging
import os
import re
import sys
import time
from ctypes import wintypes
from datetime import datetime, timedelta
from pathlib import Path

import requests
import urllib3


logger = logging.getLogger(__name__)

AUTH_URL = "https://eclaim.nhso.go.th/Client/backend/api/auth"
AUTH_INFO_URL = "https://eclaim.nhso.go.th/Client/backend/api/auth/info"
AUTH_REFRESH_URL = "https://eclaim.nhso.go.th/Client/backend/api/auth/token"
SEARCH_URL = "https://eclaim.nhso.go.th/Client/backend/api/center/m-uploads/search"
DOWNLOAD_URL = "https://eclaim.nhso.go.th/eclaimapi/invoice/InvoiceReportExcelAction.do"
DOWNLOAD_VALIDATED_MENU_URL = "^/service/download-validated$"
CLIENT_URL = "https://eclaim.nhso.go.th/Client/"
DOWNLOAD_CONNECT_TIMEOUT = 30
DOWNLOAD_READ_TIMEOUT = 180
DOWNLOAD_MAX_ATTEMPTS = 4
DOWNLOAD_RETRY_DELAYS = (5, 10, 20)
DOWNLOAD_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def config_path():
    appdata = os.getenv("APPDATA") or str(Path.home())
    return Path(appdata) / "AutoRepNHSO" / "settings.dat"


def sso_token_path():
    return config_path().with_name("sso_token.dat")


def load_settings(path):
    path = Path(path)
    if not path.exists():
        return {}
    raw = path.read_text(encoding="utf-8").strip()
    if raw.startswith("{"):
        return json.loads(raw)
    return json.loads(base64.b64decode(raw).decode("utf-8"))


def validate_download_request(
    start,
    end,
    dest_path,
    page_size,
    hcode=None,
    legacy_login=False,
    username="",
    password="",
):
    """Validate and normalize inputs shared by CLI and future web callers."""
    if not isinstance(start, str) or not start.strip():
        raise ValueError("Missing start date")
    start = start.strip()
    try:
        start_dt = datetime.strptime(start, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("Start date must use YYYY-MM-DD format") from exc

    if end is None or (isinstance(end, str) and not end.strip()):
        end = datetime.now().strftime("%Y-%m-%d")
    if not isinstance(end, str):
        raise ValueError("End date must use YYYY-MM-DD format")
    end = end.strip()
    try:
        end_dt = datetime.strptime(end, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("End date must use YYYY-MM-DD format") from exc
    if start_dt > end_dt:
        raise ValueError("Start date must not be after end date")

    if dest_path is None or not str(dest_path).strip():
        raise ValueError("Destination path must not be empty")
    destination = Path(dest_path)

    if isinstance(page_size, bool) or not isinstance(page_size, int) or page_size <= 0:
        raise ValueError("Page size must be greater than zero")
    if hcode is not None and str(hcode).strip() and not re.fullmatch(r"\d{5}", str(hcode).strip()):
        raise ValueError("Hospital code must contain exactly 5 digits")
    if legacy_login and (not username or not password):
        raise ValueError("Missing username/password in settings for --legacy-login")

    return {
        "start": start,
        "end": end,
        "destination": destination,
        "page_size": page_size,
        "hcode": str(hcode).strip() if hcode is not None else "",
    }


def _emit_log(log_callback, message, level="info"):
    log_method = getattr(logger, level, logger.info)
    log_method(message)
    if log_callback:
        log_callback(message, level=level)


def _emit_progress(progress_callback, event):
    if progress_callback:
        progress_callback(event)


def allowed_date_tokens(start_str, end_str):
    start_dt = datetime.strptime(start_str, "%Y-%m-%d")
    end_dt = datetime.strptime(end_str, "%Y-%m-%d") if end_str else datetime.now()
    tokens = set()
    curr = start_dt
    while curr <= end_dt:
        tokens.add(f"{curr.year + 543}{curr:%m%d}")
        curr += timedelta(days=1)
    return tokens


def month_year_from_filename(filename):
    match = re.search(r"(25\d{2})(\d{2})(\d{2})", filename)
    if not match:
        return "", ""
    return match.group(2), match.group(1)


def output_name(filename):
    return filename.replace(".ecd", "_REP.xls").replace(".ECD", "_REP.xls")


def is_safe_source_filename(filename):
    """Return whether an NHSO filename is a single local file name."""
    if not filename or filename in {".", ".."} or "\x00" in filename:
        return False
    return Path(filename).name == filename and "/" not in filename and "\\" not in filename


def is_ready(item):
    return item.get("loaded") == "Y" or item.get("dataStatus") == "1"


def login(session, username, password):
    response = session.post(AUTH_URL, json={"username": username, "password": password}, timeout=60)
    response.raise_for_status()
    token = response.json().get("token")
    if not token:
        raise RuntimeError("Login succeeded but API did not return token")
    return token


def protect_token(token):
    raw = token.encode("utf-8")
    raw_buffer = ctypes.create_string_buffer(raw)
    input_blob = DataBlob(len(raw), ctypes.cast(raw_buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output_blob = DataBlob()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "NHSO e-Claim SSO token",
        None,
        None,
        None,
        1,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def unprotect_token(encrypted):
    encrypted_buffer = ctypes.create_string_buffer(encrypted)
    input_blob = DataBlob(
        len(encrypted), ctypes.cast(encrypted_buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = DataBlob()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 1, ctypes.byref(output_blob)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)


def save_sso_token(path, token):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(protect_token(token))


def load_sso_token(path):
    path = Path(path)
    if not path.exists():
        return None
    try:
        return unprotect_token(path.read_bytes())
    except (OSError, UnicodeDecodeError) as exc:
        raise RuntimeError(f"Cannot read saved SSO token {path}: {exc}") from exc


def browser_sso_login(token_path, timeout_seconds=600, log_callback=None):
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError("Playwright is required for --sso-login: pip install playwright") from exc

    profile_dir = Path(token_path).with_name("sso_browser_profile")
    chrome_path = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    launch_options = {
        "user_data_dir": str(profile_dir),
        "headless": False,
        "ignore_https_errors": True,
        "no_viewport": True,
        "args": ["--start-maximized"],
    }
    if chrome_path.exists():
        launch_options["executable_path"] = str(chrome_path)

    _emit_log(log_callback, "Chrome is opening. Complete NHSO OSS login in that window.")
    _emit_log(
        log_callback,
        f"Waiting up to {timeout_seconds // 60} minutes for SSO login...",
    )
    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(**launch_options)
        try:
            pages = context.pages
            page = pages[0] if pages else context.new_page()
            page.goto(CLIENT_URL, wait_until="domcontentloaded", timeout=120_000)
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                for current_page in context.pages:
                    if not current_page.url.startswith("https://eclaim.nhso.go.th/Client"):
                        continue
                    try:
                        token = current_page.evaluate("localStorage.getItem('token')")
                    except PlaywrightError:
                        continue
                    if token:
                        save_sso_token(token_path, token)
                        _emit_log(log_callback, f"SSO login saved securely to {token_path}")
                        return token
                if not context.pages:
                    raise RuntimeError("Chrome was closed before SSO login completed")
                time.sleep(1)
        finally:
            context.close()
    raise RuntimeError("Timed out waiting for NHSO OSS login")


def refresh_token(session, token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    response = session.post(AUTH_REFRESH_URL, json={"token": token}, headers=headers, timeout=60)
    response.raise_for_status()
    refreshed = response.json().get("token")
    if not refreshed:
        raise RuntimeError("NHSO token refresh did not return a token")
    return refreshed


def find_menu_id(nodes, url):
    for node in nodes or []:
        ref_menu = node.get("refMenu") or node
        if ref_menu.get("url") == url:
            return ref_menu.get("id")
        found = find_menu_id(node.get("children"), url)
        if found:
            return found
    return None


def auth_info(session, headers, token):
    response = session.post(AUTH_INFO_URL, json={"token": token}, headers=headers, timeout=60)
    response.raise_for_status()
    return response.json()


def search_page(session, headers, hcode, page, page_size):
    payload = {
        "page": page,
        "size": page_size,
        "where": [],
        "sort": [{"name": "uploadId", "type": "DESC"}],
        "isCount": True,
        "hcode": hcode,
    }
    response = session.post(SEARCH_URL, json=payload, headers=headers, timeout=60)
    if response.status_code >= 400:
        detail = response.text[:1000].replace("\r", " ").replace("\n", " ")
        raise RuntimeError(f"Search API failed on page {page}: HTTP {response.status_code} {detail}")
    body = response.json()
    data = body.get("data") or []
    if not isinstance(data, list):
        raise RuntimeError("Search API returned unexpected data format")
    return data, body


def download_file(
    session, headers, token, hcode, item, dest_dir, overwrite, log_callback=None
):
    source_name = item["filename"]
    if not is_safe_source_filename(source_name):
        return "invalid_filename", ""
    dest_name = output_name(source_name)
    dest = dest_dir / dest_name
    if dest.exists() and not overwrite:
        return "exists", dest_name

    month, year = month_year_from_filename(source_name)
    params = {
        "status": "excel",
        "filename": source_name,
        "zphid": hcode,
        "level": "H",
        "month": month,
        "year": year,
        "token": token,
    }
    response = None
    for attempt in range(1, DOWNLOAD_MAX_ATTEMPTS + 1):
        try:
            response = session.get(
                DOWNLOAD_URL,
                params=params,
                headers=headers,
                timeout=(DOWNLOAD_CONNECT_TIMEOUT, DOWNLOAD_READ_TIMEOUT),
            )
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            if attempt == DOWNLOAD_MAX_ATTEMPTS:
                _emit_log(
                    log_callback,
                    f"warning: download failed after {attempt} attempts: "
                    f"{dest_name} ({type(exc).__name__})",
                    "warning",
                )
                return f"network_error_after_{attempt}_attempts", dest_name
            delay = DOWNLOAD_RETRY_DELAYS[attempt - 1]
            _emit_log(
                log_callback,
                f"warning: download attempt {attempt}/{DOWNLOAD_MAX_ATTEMPTS} failed: "
                f"{dest_name} ({type(exc).__name__}); retrying in {delay} seconds...",
                "warning",
            )
            time.sleep(delay)
            continue

        if response.status_code not in DOWNLOAD_RETRY_STATUS_CODES:
            break
        if attempt == DOWNLOAD_MAX_ATTEMPTS:
            break
        delay = DOWNLOAD_RETRY_DELAYS[attempt - 1]
        _emit_log(
            log_callback,
            f"warning: NHSO returned HTTP {response.status_code} for {dest_name}; "
            f"retrying in {delay} seconds...",
            "warning",
        )
        response.close()
        response = None
        time.sleep(delay)

    if response is None:
        return "network_error", dest_name
    try:
        if response.status_code != 200:
            return f"http_{response.status_code}", dest_name

        content = response.content
        content_lower = content[:500].lower()
        if b"<html" in content_lower or b"password" in content_lower:
            return "html_or_session_expired", dest_name

        tmp = dest.with_suffix(dest.suffix + ".part")
        tmp.write_bytes(content)
        tmp.replace(dest)
        return "downloaded", dest_name
    finally:
        response.close()


def build_parser():
    """Build the backward-compatible command-line parser."""
    parser = argparse.ArgumentParser(description="Download NHSO REP files with API pagination.")
    parser.add_argument(
        "--config",
        default=str(config_path()),
        help="Optional path to AutoRepNHSO settings.dat or a JSON settings file.",
    )
    parser.add_argument("--hcode", help="Hospital code. Defaults to settings or the SSO account.")
    parser.add_argument("--start", help="Start date YYYY-MM-DD. Defaults to saved setting.")
    parser.add_argument("--end", help="End date YYYY-MM-DD. Defaults to saved setting or today.")
    parser.add_argument("--path", help="Download folder. Defaults to saved setting.")
    parser.add_argument("--page-size", type=int, default=3000)
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    parser.add_argument("--dry-run", action="store_true", help="List matching files without downloading.")
    parser.add_argument("--insecure", action="store_true", help="Disable SSL certificate verification.")
    parser.add_argument(
        "--sso-login",
        action="store_true",
        help="Open Chrome for NHSO OSS login and securely save the SSO token.",
    )
    parser.add_argument(
        "--legacy-login",
        action="store_true",
        help="Use the old username/password API instead of NHSO OSS SSO.",
    )
    return parser


def download_rep(
    start,
    end=None,
    dest_path=None,
    hcode=None,
    page_size=3000,
    overwrite=False,
    dry_run=False,
    insecure=False,
    sso_login=False,
    legacy_login=False,
    config=None,
    progress_callback=None,
    log_callback=None,
):
    """Search and optionally download NHSO REP files, returning structured results."""
    settings = load_settings(config or config_path())
    username = settings.get("username", "")
    password = settings.get("password", "")
    hcode = hcode or settings.get("hcode", "")
    start = start or settings.get("start_date", "")
    end = end if end is not None else settings.get("end_date", "")
    dest_path = dest_path or settings.get("path") or r"C:\TEMP\REP"
    overwrite = bool(overwrite or settings.get("overwrite"))
    validated = validate_download_request(
        start=start,
        end=end,
        dest_path=dest_path,
        page_size=page_size,
        hcode=hcode,
        legacy_login=legacy_login,
        username=username,
        password=password,
    )
    start = validated["start"]
    end = validated["end"]
    dest_dir = validated["destination"]
    hcode = validated["hcode"]
    dest_dir.mkdir(parents=True, exist_ok=True)
    dates = allowed_date_tokens(start, end)

    session = requests.Session()
    session.verify = not insecure
    if insecure:
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    warnings = []
    errors = []
    files = []
    stats = {
        "pages": 0,
        "seen": 0,
        "matched": 0,
        "date_skipped": 0,
        "status_skipped": 0,
        "exists": 0,
        "downloaded": 0,
        "failed": 0,
    }

    try:
        token_file = sso_token_path()
        if sso_login:
            token = browser_sso_login(token_file, log_callback=log_callback)
        elif legacy_login:
            token = login(session, username, password)
        else:
            token = load_sso_token(token_file)
            if not token:
                raise RuntimeError(
                    "No NHSO SSO session is saved. Run this command once with --sso-login."
                )
            try:
                token = refresh_token(session, token)
                save_sso_token(token_file, token)
            except requests.RequestException as exc:
                raise RuntimeError(
                    "Saved NHSO SSO session has expired. Run this command again with "
                    f"--sso-login. ({exc})"
                ) from exc

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        info = auth_info(session, headers, token)
        menu_id = find_menu_id(info.get("menus"), DOWNLOAD_VALIDATED_MENU_URL)
        if menu_id:
            headers["C-Menu"] = menu_id

        user_hospital = (info.get("user") or {}).get("refHospital") or {}
        user_hcode = str(user_hospital.get("hmain") or "")
        if not hcode:
            hcode = user_hcode
        if not hcode:
            raise RuntimeError(
                "No hospital code was found in arguments, settings, or the SSO account"
            )
        if not re.fullmatch(r"\d{5}", hcode):
            raise ValueError("Hospital code must contain exactly 5 digits")
        if user_hcode and user_hcode != hcode:
            warning = (
                f"settings hcode {hcode} differs from login hospital hcode {user_hcode}"
            )
            warnings.append(warning)
            _emit_log(log_callback, f"warning: {warning}", "warning")

        page = 0
        last_total_size = None
        while True:
            items, search_meta = search_page(session, headers, hcode, page, page_size)
            last_total_size = search_meta.get("totalSize")
            stats["pages"] += 1
            stats["seen"] += len(items)
            _emit_log(
                log_callback,
                f"page {page}: {len(items)} records (totalSize={last_total_size})",
            )
            _emit_progress(
                progress_callback,
                {"event": "page_loaded", "page": page, "stats": stats.copy()},
            )

            if not items:
                break

            for item in items:
                filename = item.get("filename") or ""
                if not any(date_token in filename for date_token in dates):
                    stats["date_skipped"] += 1
                    continue
                if not is_ready(item):
                    stats["status_skipped"] += 1
                    continue

                stats["matched"] += 1
                if not is_safe_source_filename(filename):
                    stats["failed"] += 1
                    errors.append(f"{filename}: invalid_filename")
                    file_result = {
                        "source_name": filename,
                        "output_name": "",
                        "result": "invalid_filename",
                        "exists": False,
                    }
                    files.append(file_result)
                    _emit_log(log_callback, "invalid_filename: rejected NHSO source name", "error")
                    _emit_progress(
                        progress_callback,
                        {"event": "file_result", "file": file_result, "stats": stats.copy()},
                    )
                    continue
                dest_name = output_name(filename)
                if dry_run:
                    destination_exists = (dest_dir / dest_name).exists()
                    if destination_exists:
                        stats["exists"] += 1
                        result = "overwrite" if overwrite else "exists"
                    else:
                        result = "matched"
                    _emit_log(log_callback, f"{result}: {dest_name}")
                else:
                    destination_exists = (dest_dir / dest_name).exists()
                    result, dest_name = download_file(
                        session,
                        headers,
                        token,
                        hcode,
                        item,
                        dest_dir,
                        overwrite,
                        log_callback,
                    )
                    if result == "downloaded":
                        stats["downloaded"] += 1
                    elif result == "exists":
                        stats["exists"] += 1
                    else:
                        stats["failed"] += 1
                        errors.append(f"{dest_name}: {result}")
                    _emit_log(log_callback, f"{result}: {dest_name}")

                file_result = {
                    "source_name": filename,
                    "output_name": dest_name,
                    "result": result,
                    "exists": destination_exists,
                }
                files.append(file_result)
                _emit_progress(
                    progress_callback,
                    {"event": "file_result", "file": file_result, "stats": stats.copy()},
                )

            if len(items) < page_size:
                break
            page += 1
            time.sleep(0.3)

        if stats["seen"] == 0:
            warning = (
                f"No REP upload records were returned by NHSO for hcode={hcode}, "
                f"start={start}, end={end}, totalSize={last_total_size}."
            )
            warnings.append(warning)
            _emit_log(log_callback, warning, "warning")
            _emit_log(
                log_callback,
                "Open the NHSO menu 'รับชุดข้อมูลผลการตรวจสอบ (REP)' with the "
                "same account to confirm that records exist.",
                "warning",
            )

        status = "completed_with_errors" if stats["failed"] else "completed"
        return {
            "success": stats["failed"] == 0,
            "status": status,
            "hcode": hcode,
            "start_date": start,
            "end_date": end,
            "destination": str(dest_dir),
            "dry_run": bool(dry_run),
            "overwrite": overwrite,
            "stats": stats,
            "files": files,
            "warnings": warnings,
            "errors": errors,
        }
    finally:
        session.close()


def main(argv=None):
    """Run the CLI adapter and return the service result."""
    args = build_parser().parse_args(argv)

    def cli_log(message, level="info"):
        print(message)

    result = download_rep(
        start=args.start,
        end=args.end,
        dest_path=args.path,
        hcode=args.hcode,
        page_size=args.page_size,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
        insecure=args.insecure,
        sso_login=args.sso_login,
        legacy_login=args.legacy_login,
        config=args.config,
        log_callback=cli_log,
    )
    print(json.dumps(result["stats"], ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    try:
        main()
    except requests.exceptions.SSLError as exc:
        print(f"SSL error: {exc}", file=sys.stderr)
        print("If this only happens on your network, rerun with --insecure.", file=sys.stderr)
        raise SystemExit(2)
    except (ValueError, RuntimeError, requests.RequestException, OSError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
