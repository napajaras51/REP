"""SQLite persistence for download job metadata and file results."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


SCHEMA_VERSION = 1


def default_database_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    return project_root / "data" / "app.db"


class HistoryStore:
    """Persist sanitized download history without credentials or REP content."""

    def __init__(self, path=None):
        self.path = Path(path or default_database_path())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS download_jobs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    hcode TEXT,
                    dry_run INTEGER NOT NULL DEFAULT 0,
                    overwrite INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL,
                    pages INTEGER NOT NULL DEFAULT 0,
                    seen INTEGER NOT NULL DEFAULT 0,
                    matched INTEGER NOT NULL DEFAULT 0,
                    date_skipped INTEGER NOT NULL DEFAULT 0,
                    status_skipped INTEGER NOT NULL DEFAULT 0,
                    exists_count INTEGER NOT NULL DEFAULT 0,
                    downloaded INTEGER NOT NULL DEFAULT 0,
                    failed INTEGER NOT NULL DEFAULT 0,
                    error_code TEXT,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS download_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    source_name TEXT,
                    output_name TEXT,
                    result TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(job_id) REFERENCES download_jobs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_download_jobs_created_at
                    ON download_jobs(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_download_files_job_id
                    ON download_files(job_id);
                """
            )
            connection.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def create_job(self, snapshot: dict) -> None:
        request = snapshot["request"]
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO download_jobs (
                    id, created_at, start_date, end_date, destination, hcode,
                    dry_run, overwrite, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot["job_id"],
                    snapshot["created_at"],
                    request["start_date"],
                    request["end_date"],
                    request["destination"],
                    request.get("hcode"),
                    int(bool(request.get("dry_run", False))),
                    int(bool(request.get("overwrite", False))),
                    snapshot["status"],
                ),
            )

    def mark_started(self, snapshot: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                "UPDATE download_jobs SET status = ?, started_at = ? WHERE id = ?",
                (snapshot["status"], snapshot["started_at"], snapshot["job_id"]),
            )

    def update_progress(self, job_id: str, stats: dict) -> None:
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE download_jobs SET
                    pages = ?, seen = ?, matched = ?, date_skipped = ?,
                    status_skipped = ?, exists_count = ?, downloaded = ?, failed = ?
                WHERE id = ?
                """,
                self._stats_values(stats) + (job_id,),
            )

    def complete_job(self, snapshot: dict) -> None:
        stats = snapshot.get("progress") or {}
        error = snapshot.get("error") or {}
        files = (snapshot.get("result") or {}).get("files") or []
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE download_jobs SET
                    status = ?, completed_at = ?, pages = ?, seen = ?, matched = ?,
                    date_skipped = ?, status_skipped = ?, exists_count = ?,
                    downloaded = ?, failed = ?, error_code = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    snapshot["status"],
                    snapshot["completed_at"],
                )
                + self._stats_values(stats)
                + (
                    error.get("code"),
                    error.get("message"),
                    snapshot["job_id"],
                ),
            )
            connection.execute(
                "DELETE FROM download_files WHERE job_id = ?",
                (snapshot["job_id"],),
            )
            connection.executemany(
                """
                INSERT INTO download_files (
                    job_id, source_name, output_name, result, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot["job_id"],
                        item.get("source_name"),
                        item.get("output_name"),
                        item.get("result"),
                        snapshot["completed_at"],
                    )
                    for item in files
                ],
            )

    def list_jobs(self, limit: int = 100, offset: int = 0) -> list[dict]:
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM download_jobs
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [self._job_row(row) for row in rows]

    def get_job(self, job_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM download_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if row is None:
                return None
            files = connection.execute(
                """
                SELECT source_name, output_name, result, created_at
                FROM download_files WHERE job_id = ? ORDER BY id
                """,
                (job_id,),
            ).fetchall()
        result = self._job_row(row)
        result["files"] = [dict(item) for item in files]
        return result

    @staticmethod
    def _stats_values(stats: dict) -> tuple:
        return (
            int(stats.get("pages", 0)),
            int(stats.get("seen", 0)),
            int(stats.get("matched", 0)),
            int(stats.get("date_skipped", 0)),
            int(stats.get("status_skipped", 0)),
            int(stats.get("exists", 0)),
            int(stats.get("downloaded", 0)),
            int(stats.get("failed", 0)),
        )

    @staticmethod
    def _job_row(row: sqlite3.Row) -> dict:
        data = dict(row)
        data["dry_run"] = bool(data["dry_run"])
        data["overwrite"] = bool(data["overwrite"])
        data["stats"] = {
            "pages": data.pop("pages"),
            "seen": data.pop("seen"),
            "matched": data.pop("matched"),
            "date_skipped": data.pop("date_skipped"),
            "status_skipped": data.pop("status_skipped"),
            "exists": data.pop("exists_count"),
            "downloaded": data.pop("downloaded"),
            "failed": data.pop("failed"),
        }
        return data
