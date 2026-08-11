"""Private append-only SQLite persistence for narrative research packages."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from threading import RLock

from ..identity import canonical_json, utc_datetime, utc_now
from .research_package import NarrativeResearchPackage, RESEARCH_PACKAGE_SCHEMA


SCHEMA = """
CREATE TABLE IF NOT EXISTS narrative_research_packages (
    package_id TEXT PRIMARY KEY,
    schema_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    trigger_id TEXT NOT NULL,
    triggered_at TEXT NOT NULL,
    researched_at TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    authorizes_trade INTEGER NOT NULL CHECK(authorizes_trade = 0),
    document_json TEXT NOT NULL,
    inserted_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS narrative_research_trigger_idx
ON narrative_research_packages(mode, trigger_id, researched_at, package_id);
CREATE TRIGGER IF NOT EXISTS narrative_research_no_update
BEFORE UPDATE ON narrative_research_packages
BEGIN SELECT RAISE(ABORT, 'narrative research UPDATE is forbidden'); END;
CREATE TRIGGER IF NOT EXISTS narrative_research_no_delete
BEFORE DELETE ON narrative_research_packages
BEGIN SELECT RAISE(ABORT, 'narrative research DELETE is forbidden'); END;
"""


class ResearchPackageConflict(RuntimeError):
    """A content-addressed package ID already names different bytes."""


class NarrativeResearchStore:
    """Atomically append immutable research documents to a private database."""

    def __init__(
        self,
        database: str | Path,
        *,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.path = Path(database)
        if str(self.path) == ":memory:":
            raise ValueError("narrative research requires a file-backed database")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self._clock = clock
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path, isolation_level=None, timeout=5, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA foreign_keys=ON")
            self._connection.executescript(SCHEMA)
            self._secure_files()
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def __enter__(self) -> "NarrativeResearchStore":
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def append(self, package: NarrativeResearchPackage) -> bool:
        """Commit one package atomically; exact replays are idempotent."""

        document = canonical_json(package.to_payload())
        with self._lock:
            self._ensure_open()
            db = self._connection
            db.execute("BEGIN IMMEDIATE")
            try:
                row = db.execute(
                    "SELECT document_json FROM narrative_research_packages "
                    "WHERE package_id = ?",
                    (package.package_id,),
                ).fetchone()
                if row is not None:
                    if row["document_json"] != document:
                        raise ResearchPackageConflict(package.package_id)
                    db.execute("COMMIT")
                    return False
                db.execute(
                    "INSERT INTO narrative_research_packages VALUES "
                    "(?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        package.package_id,
                        RESEARCH_PACKAGE_SCHEMA,
                        package.mode.value,
                        package.trigger_id,
                        package.triggered_at.isoformat(),
                        package.researched_at.isoformat(),
                        package.status,
                        package.reason,
                        package.content_sha256,
                        0,
                        document,
                        utc_datetime(self._clock()).isoformat(),
                    ),
                )
                db.execute("COMMIT")
            except BaseException:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
            finally:
                self._secure_files()
        return True

    def get(self, package_id: str) -> dict[str, object] | None:
        with self._lock:
            self._ensure_open()
            row = self._connection.execute(
                "SELECT document_json FROM narrative_research_packages "
                "WHERE package_id = ?",
                (package_id,),
            ).fetchone()
        return None if row is None else json.loads(row["document_json"])

    def for_trigger(self, mode: str, trigger_id: str) -> tuple[dict[str, object], ...]:
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                "SELECT document_json FROM narrative_research_packages "
                "WHERE mode = ? AND trigger_id = ? "
                "ORDER BY researched_at, package_id",
                (mode, trigger_id),
            ).fetchall()
        return tuple(json.loads(row["document_json"]) for row in rows)

    def count(self) -> int:
        with self._lock:
            self._ensure_open()
            row = self._connection.execute(
                "SELECT COUNT(*) AS total FROM narrative_research_packages"
            ).fetchone()
        return int(row["total"])

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("narrative research store is closed")

    def _secure_files(self) -> None:
        for path in (self.path, Path(f"{self.path}-wal"), Path(f"{self.path}-shm")):
            if path.is_file():
                path.chmod(0o600)
