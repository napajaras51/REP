"""Start the NHSO REP web application on the local machine only."""

import argparse
import json
import threading
import time
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

from nhso_rep_webapp.app.logging_setup import configure_logging


HOST = "127.0.0.1"
PORT = 8000
APP_URL = f"http://{HOST}:{PORT}"
APP_TITLE = "NHSO REP Download Manager"


def existing_app_is_running(url: str = APP_URL) -> bool:
    """Return true only when the NHSO REP application owns the local port."""
    try:
        with urlopen(f"{url}/openapi.json", timeout=1) as response:
            payload = json.load(response)
        return response.status == 200 and payload.get("info", {}).get("title") == APP_TITLE
    except (OSError, URLError, ValueError, TypeError):
        return False


def open_browser_when_ready(
    url: str = APP_URL,
    timeout_seconds: float = 30,
    interval_seconds: float = 0.25,
    opener=webbrowser.open,
) -> bool:
    """Open the browser only after the local health endpoint responds."""
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{url}/api/health"
    while time.monotonic() < deadline:
        try:
            with urlopen(health_url, timeout=1) as response:
                if response.status == 200:
                    opener(url)
                    return True
        except (OSError, URLError):
            time.sleep(interval_seconds)
    return False


def main(argv=None) -> None:
    """Run Uvicorn with a localhost-only binding."""
    parser = argparse.ArgumentParser(description="Start NHSO REP Download Manager")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the local web application in the default browser.",
    )
    args = parser.parse_args(argv)
    if existing_app_is_running():
        print(f"NHSO REP Download Manager is already running at {APP_URL}")
        if not args.no_browser:
            webbrowser.open(APP_URL)
        return

    configure_logging()
    if not args.no_browser:
        threading.Thread(
            target=open_browser_when_ready,
            name="open-nhso-rep-browser",
            daemon=True,
        ).start()
    uvicorn.run(
        "nhso_rep_webapp.app.main:app",
        host=HOST,
        port=PORT,
        reload=False,
    )


if __name__ == "__main__":
    main()
