"""Local rotating log configuration for the Windows launcher."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(log_path=None) -> Path:
    project_root = Path(__file__).resolve().parents[2]
    path = Path(log_path or project_root / "logs" / "webapp.log")
    path.parent.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    if not any(getattr(handler, "baseFilename", None) == str(path.resolve()) for handler in root.handlers):
        handler = RotatingFileHandler(
            path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    return path
