"""Private, durable work queue for narrative research inputs only."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
import secrets
import sqlite3
from threading import RLock

from ..identity import utc_datetime, utc_now
from .job_payloads import NarrativeJobInput, encode_job_input
from .job_queue_models import (
    JobContentConflict,
    JobStatus,
    LeaseLostError,
    NarrativeJob,
    job_from_row,
    lease_identity,
    sanitized_error_type,
    worker_identity,
)
from .job_queue_priority import reprioritize_pending_rows
from .job_queue_schema import SCHEMA, prepare_queue_schema
from .job_queue_sqlite import (
    immediate_transaction,
    prepare_private_database,
    secure_sqlite_files,
)


class NarrativeJobQueue:
    """SQLite queue separating fast collection from slower Grok research."""

    def __init__(
        self, database: str | Path, *, clock: Callable[[], datetime] = utc_now
    ) -> None:
        self.path = Path(database)
        if str(database) == ":memory:" or str(database).startswith("file:"):
            raise ValueError("narrative job queue requires a file-backed database")
        prepare_private_database(self.path)
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
            prepare_queue_schema(self._connection)
            secure_sqlite_files(self.path)
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def __enter__(self) -> "NarrativeJobQueue":
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def enqueue(
        self,
        payload: NarrativeJobInput,
        *,
        max_attempts: int = 3,
        priority: int = 50,
        available_at: datetime | None = None,
    ) -> str:
        """Persist an input once and return its deterministic content ID."""

        if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        if type(priority) is not int or not 1 <= priority <= 100:
            raise ValueError("priority must be between 1 and 100")
        job_id, kind, content_sha256, document = encode_job_input(payload)
        now = self._now()
        ready = utc_datetime(available_at) if available_at else now
        with self._transaction() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO narrative_jobs "
                "(job_id,kind,priority,content_sha256,payload_json,status,attempts,"
                "max_attempts,available_at,created_at,updated_at) "
                "VALUES (?,?,?,?,?,'pending',0,?,?,?,?)",
                (
                    job_id,
                    kind,
                    priority,
                    content_sha256,
                    document,
                    max_attempts,
                    ready.isoformat(),
                    now.isoformat(),
                    now.isoformat(),
                ),
            ).rowcount
            if not inserted:
                row = db.execute(
                    "SELECT kind,content_sha256 FROM narrative_jobs WHERE job_id=?",
                    (job_id,),
                ).fetchone()
                if (
                    row is None
                    or row["kind"] != kind
                    or row["content_sha256"] != content_sha256
                ):
                    raise JobContentConflict(job_id)
                db.execute(
                    "UPDATE narrative_jobs SET priority=MIN(priority,?),"
                    "payload_json=?,updated_at=? "
                    "WHERE job_id=? AND status='pending'",
                    (priority, document, now.isoformat(), job_id),
                )
        return job_id

    def claim(self, worker: str, *, lease_seconds: float = 60) -> NarrativeJob | None:
        """Atomically recover expired work and lease the oldest ready job."""

        owner = worker_identity(worker)
        if isinstance(lease_seconds, bool) or not 0 < lease_seconds <= 86_400:
            raise ValueError("lease_seconds must be in (0, 86400]")
        now = self._now()
        expires = now + timedelta(seconds=lease_seconds)
        lease_id = secrets.token_hex(16)
        with self._transaction() as db:
            self._recover_expired(db, now)
            row = db.execute(
                "SELECT job_id FROM narrative_jobs "
                "WHERE status='pending' AND available_at<=? AND attempts<max_attempts "
                "ORDER BY priority,created_at DESC,available_at,job_id LIMIT 1",
                (now.isoformat(),),
            ).fetchone()
            if row is None:
                return None
            changed = db.execute(
                "UPDATE narrative_jobs SET status='leased',attempts=attempts+1,"
                "lease_owner=?,lease_id=?,lease_expires_at=?,error_type=NULL,updated_at=? "
                "WHERE job_id=? AND status='pending'",
                (
                    owner,
                    lease_id,
                    expires.isoformat(),
                    now.isoformat(),
                    row["job_id"],
                ),
            ).rowcount
            if changed != 1:
                raise RuntimeError("atomic narrative job claim failed")
            leased = db.execute(
                "SELECT * FROM narrative_jobs WHERE job_id=?", (row["job_id"],)
            ).fetchone()
        return job_from_row(leased)

    def ack(self, job_id: str, worker: str, lease_id: str) -> NarrativeJob:
        """Atomically mark a currently owned, unexpired lease complete."""

        owner = worker_identity(worker)
        token = lease_identity(lease_id)
        now = self._now()
        with self._transaction() as db:
            self._recover_expired(db, now)
            changed = db.execute(
                "UPDATE narrative_jobs SET status='done',lease_owner=NULL,lease_id=NULL,"
                "lease_expires_at=NULL,error_type=NULL,updated_at=?,completed_at=? "
                "WHERE job_id=? AND status='leased' AND lease_owner=? AND lease_id=?",
                (now.isoformat(), now.isoformat(), job_id, owner, token),
            ).rowcount
            if changed != 1:
                raise LeaseLostError(job_id)
            row = db.execute(
                "SELECT * FROM narrative_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return job_from_row(row)

    def fail(
        self,
        job_id: str,
        worker: str,
        lease_id: str,
        error: BaseException | type[BaseException],
        *,
        retry: bool = True,
        retry_delay_seconds: float = 0,
    ) -> NarrativeJob:
        """Release or terminate a lease while retaining only the error class."""

        owner = worker_identity(worker)
        token = lease_identity(lease_id)
        error_type = sanitized_error_type(error)
        if isinstance(retry_delay_seconds, bool) or not 0 <= retry_delay_seconds <= 86_400:
            raise ValueError("retry_delay_seconds must be in [0, 86400]")
        now = self._now()
        with self._transaction() as db:
            self._recover_expired(db, now)
            row = db.execute(
                "SELECT attempts,max_attempts FROM narrative_jobs "
                "WHERE job_id=? AND status='leased' AND lease_owner=? AND lease_id=?",
                (job_id, owner, token),
            ).fetchone()
            if row is None:
                raise LeaseLostError(job_id)
            terminal = not retry or row["attempts"] >= row["max_attempts"]
            status = "failed" if terminal else "pending"
            ready = now + timedelta(seconds=retry_delay_seconds)
            completed = now.isoformat() if terminal else None
            db.execute(
                "UPDATE narrative_jobs SET status=?,available_at=?,lease_owner=NULL,lease_id=NULL,"
                "lease_expires_at=NULL,error_type=?,updated_at=?,completed_at=? "
                "WHERE job_id=? AND status='leased' AND lease_id=?",
                (
                    status,
                    ready.isoformat(),
                    error_type,
                    now.isoformat(),
                    completed,
                    job_id,
                    token,
                ),
            )
            updated = db.execute(
                "SELECT * FROM narrative_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return job_from_row(updated)

    def get(self, job_id: str) -> NarrativeJob | None:
        with self._lock:
            self._ensure_open()
            row = self._connection.execute(
                "SELECT * FROM narrative_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
        return None if row is None else job_from_row(row)

    def counts(self) -> dict[JobStatus, int]:
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                "SELECT status,COUNT(*) AS total FROM narrative_jobs GROUP BY status"
            ).fetchall()
        found = {JobStatus(row["status"]): int(row["total"]) for row in rows}
        return {status: found.get(status, 0) for status in JobStatus}

    def reprioritize_pending(
        self, priority_for: Callable[[NarrativeJobInput], int]
    ) -> int:
        """Reapply the current application policy to all unclaimed work."""

        with self._transaction() as db:
            return reprioritize_pending_rows(
                db, priority_for, updated_at=self._now().isoformat()
            )

    def _recover_expired(self, db: sqlite3.Connection, now: datetime) -> None:
        stamp = now.isoformat()
        db.execute(
            "UPDATE narrative_jobs SET status='failed',lease_owner=NULL,lease_id=NULL,"
            "lease_expires_at=NULL,error_type='LeaseExpired',updated_at=?,completed_at=? "
            "WHERE status='leased' AND lease_expires_at<=? AND attempts>=max_attempts",
            (stamp, stamp, stamp),
        )
        db.execute(
            "UPDATE narrative_jobs SET status='pending',available_at=?,lease_owner=NULL,"
            "lease_id=NULL,"
            "lease_expires_at=NULL,error_type='LeaseExpired',updated_at=? "
            "WHERE status='leased' AND lease_expires_at<=? AND attempts<max_attempts",
            (stamp, stamp, stamp),
        )

    def _transaction(self):
        self._ensure_open()
        return immediate_transaction(
            self._connection, self._lock, lambda: secure_sqlite_files(self.path)
        )

    def _now(self) -> datetime:
        return utc_datetime(self._clock())

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("narrative job queue is closed")
