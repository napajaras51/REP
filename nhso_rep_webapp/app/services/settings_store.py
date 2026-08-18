"""Separate, credential-free settings storage for the local web app."""

import json
import threading
from datetime import date
from pathlib import Path


ALLOWED_KEYS = {
    "default_destination",
    "default_page_size",
    "default_insecure",
    "last_start_date",
    "last_end_date",
}


def default_settings_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "webapp_settings.json"


class SettingsStore:
    """Read and atomically update non-secret web application settings."""

    def __init__(self, path=None, default_destination=r"C:\TEMP\REP"):
        self.path = Path(path or default_settings_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._defaults = {
            "default_destination": str(default_destination),
            "default_page_size": 3000,
            "default_insecure": False,
            "last_start_date": None,
            "last_end_date": None,
        }

    def get(self) -> dict:
        with self._lock:
            if not self.path.exists():
                return self._defaults.copy()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                raise RuntimeError("Unable to read web application settings") from exc
            if not isinstance(raw, dict):
                raise RuntimeError("Web application settings must be a JSON object")
            return {**self._defaults, **{key: raw[key] for key in ALLOWED_KEYS if key in raw}}

    def save(self, values: dict) -> dict:
        with self._lock:
            unknown = set(values) - ALLOWED_KEYS
            if unknown:
                raise ValueError("Unsupported settings fields")
            settings = {**self.get(), **values}
            safe_settings = {key: settings.get(key) for key in ALLOWED_KEYS}
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            try:
                temporary.write_text(
                    json.dumps(safe_settings, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                temporary.replace(self.path)
            except OSError as exc:
                raise RuntimeError("Unable to save web application settings") from exc
            return {**self._defaults, **safe_settings}

    def update_recent(self, start_date: date, end_date: date) -> None:
        self.save(
            {
                "last_start_date": start_date.isoformat(),
                "last_end_date": end_date.isoformat(),
            }
        )
