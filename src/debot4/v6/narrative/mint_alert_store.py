"""Bounded SQLite outbox for accepted catalyst-to-mint alerts."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from threading import RLock

from ..identity import utc_datetime, utc_now
from .catalyst_mint import CatalystMintMatch
from .job_queue_sqlite import (
    immediate_transaction,
    prepare_private_database,
    secure_sqlite_files,
)
from .mint_alert import MINT_ALERT_SLA_SECONDS, MintAlert
from .mint_alert_store_codec import (
    MintAlertStoreError,
    alert_from_row,
    insert_values,
)


TABLE = "catalyst_mint_alerts"
DEFAULT_MAX_DATABASE_BYTES = 64 * 1_024 * 1_024
INSERT_COLUMNS = """
alert_id,match_id,exact_ca,token_stage,match_kind,catalyst_tweet_id,catalyst_author,
catalyst_text,catalyst_created_at,catalyst_fetched_at,token_created_at,
match_observed_at,token_name,token_symbol,provider_fdv_usd,launchpad,
token_description,token_social_urls_json,token_status_url,raised_at,next_attempt_at
"""
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    alert_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL UNIQUE,
    exact_ca TEXT NOT NULL UNIQUE,
    token_stage TEXT NOT NULL,
    match_kind TEXT NOT NULL,
    catalyst_tweet_id TEXT NOT NULL,
    catalyst_author TEXT NOT NULL,
    catalyst_text TEXT NOT NULL,
    catalyst_created_at TEXT NOT NULL,
    catalyst_fetched_at TEXT NOT NULL,
    token_created_at TEXT NOT NULL,
    match_observed_at TEXT NOT NULL,
    token_name TEXT,
    token_symbol TEXT,
    provider_fdv_usd TEXT,
    launchpad TEXT,
    token_description TEXT,
    token_social_urls_json TEXT NOT NULL,
    token_status_url TEXT NOT NULL,
    raised_at TEXT NOT NULL,
    delivery_attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_delivery_error_type TEXT,
    delivered_at TEXT,
    authorizes_trade INTEGER NOT NULL DEFAULT 0 CHECK(authorizes_trade = 0)
);
CREATE INDEX IF NOT EXISTS catalyst_mint_alerts_delivery_idx
ON {TABLE}(delivered_at,next_attempt_at,catalyst_created_at);
CREATE INDEX IF NOT EXISTS catalyst_mint_alerts_raised_idx
ON {TABLE}(raised_at DESC,alert_id DESC);
PRAGMA user_version=2;
"""


@dataclass(frozen=True, slots=True)
class MintAlertWrite:
    created: tuple[MintAlert, ...] = ()
    duplicates: int = 0

    @property
    def inserted(self) -> int:
        return len(self.created)


class MintAlertStore:
    """Persist one retryable alert per CA after a qualifying match exists."""

    def __init__(
        self,
        database: str | Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        retention: timedelta = timedelta(days=7),
        max_rows: int = 20_000,
        max_database_bytes: int = DEFAULT_MAX_DATABASE_BYTES,
    ) -> None:
        if not timedelta(hours=1) <= retention <= timedelta(days=30):
            raise ValueError("mint alert retention must be between 1 hour and 30 days")
        if isinstance(max_rows, bool) or not 100 <= max_rows <= 100_000:
            raise ValueError("mint alert row limit must be between 100 and 100000")
        if (
            isinstance(max_database_bytes, bool)
            or not 8 * 1_024 * 1_024
            <= max_database_bytes <= 256 * 1_024 * 1_024
        ):
            raise ValueError("mint alert database byte limit is invalid")
        self.path = Path(database)
        if str(database) == ":memory:" or str(database).startswith("file:"):
            raise ValueError("mint alerts require a file-backed database")
        prepare_private_database(self.path)
        self.clock = clock
        self.retention = retention
        self.max_rows = max_rows
        self.max_database_bytes = int(max_database_bytes)
        self._lock = RLock()
        self._closed = False
        self._connection = sqlite3.connect(
            self.path, isolation_level=None, timeout=5, check_same_thread=False
        )
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA journal_size_limit=1048576")
            self._connection.execute("PRAGMA wal_autocheckpoint=100")
            self._apply_page_limit()
            self._connection.executescript(SCHEMA)
            secure_sqlite_files(self.path)
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def __enter__(self) -> "MintAlertStore":
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def record(self, matches: Iterable[CatalystMintMatch]) -> MintAlertWrite:
        items = tuple(matches)
        if not items:
            return MintAlertWrite()
        if any(not isinstance(match, CatalystMintMatch) for match in items):
            raise TypeError("mint alerts require CatalystMintMatch evidence")
        if len(items) > 1_000:
            raise ValueError("too many mint alerts in one write")
        now = utc_datetime(self.clock())
        created: list[MintAlert] = []
        duplicates = 0
        with self._transaction() as database:
            for match in items:
                row = database.execute(
                    f"SELECT * FROM {TABLE} WHERE exact_ca=? OR match_id=?",
                    (match.exact_ca, match.match_id),
                ).fetchone()
                if row is not None:
                    existing = alert_from_row(row)
                    if existing.exact_ca != match.exact_ca:
                        raise MintAlertStoreError("mint alert identity collision")
                    duplicates += 1
                    continue
                alert = MintAlert.from_match(match, raised_at=now)
                placeholders = ",".join("?" for _ in range(21))
                database.execute(
                    f"INSERT INTO {TABLE} ({INSERT_COLUMNS}) VALUES ({placeholders})",
                    insert_values(alert),
                )
                created.append(alert)
            self._prune(database, now)
        return MintAlertWrite(tuple(created), duplicates)

    def pending(
        self, *, now: datetime | None = None, limit: int = 50,
    ) -> tuple[MintAlert, ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 500:
            raise ValueError("mint alert delivery limit must be between 1 and 500")
        current = utc_datetime(now or self.clock()).isoformat()
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                f"SELECT * FROM {TABLE} WHERE delivered_at IS NULL "
                "AND next_attempt_at<=? "
                "ORDER BY catalyst_created_at,alert_id LIMIT ?",
                (current, limit),
            ).fetchall()
        return tuple(alert_from_row(row) for row in rows)

    def mark_delivered(self, alert_id: str, delivered_at: datetime) -> None:
        delivered = utc_datetime(delivered_at).isoformat()
        with self._transaction() as database:
            changed = database.execute(
                f"UPDATE {TABLE} SET delivered_at=?,"
                "delivery_attempts=delivery_attempts+1,"
                "last_delivery_error_type=NULL "
                "WHERE alert_id=? AND delivered_at IS NULL",
                (delivered, alert_id),
            ).rowcount
            if changed != 1:
                raise MintAlertStoreError("mint alert is missing or already delivered")

    def mark_failed(
        self,
        alert_id: str,
        *,
        attempted_at: datetime,
        retry_seconds: float,
        error_type: str,
    ) -> None:
        attempted = utc_datetime(attempted_at)
        retry_at = attempted + timedelta(seconds=float(retry_seconds))
        error = str(error_type).strip()[:128] or "UnknownError"
        with self._transaction() as database:
            changed = database.execute(
                f"UPDATE {TABLE} SET delivery_attempts=delivery_attempts+1,"
                "next_attempt_at=?,last_delivery_error_type=? "
                "WHERE alert_id=? AND delivered_at IS NULL",
                (retry_at.isoformat(), error, alert_id),
            ).rowcount
            if changed != 1:
                raise MintAlertStoreError("mint alert is missing or already delivered")

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._ensure_open()
            row = self._connection.execute(
                f"SELECT COUNT(*) total,"
                "SUM(CASE WHEN delivered_at IS NULL THEN 1 ELSE 0 END) pending,"
                "SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) delivered,"
                f"MAX(raised_at) latest FROM {TABLE}"
            ).fetchone()
        return {
            "total": int(row["total"] or 0),
            "pending_delivery": int(row["pending"] or 0),
            "delivered": int(row["delivered"] or 0),
            "last_raised_at": row["latest"],
            "sla_seconds": MINT_ALERT_SLA_SECONDS,
            "trigger": "accepted_catalyst_mint_match",
            "raw_mint_triggers_alert": False,
            "rpc_on_critical_path": False,
            "model_on_critical_path": False,
            "authorizes_trade": False,
        }

    def _apply_page_limit(self) -> None:
        page_size = int(self._connection.execute("PRAGMA page_size").fetchone()[0])
        page_limit = self.max_database_bytes // page_size
        configured = int(self._connection.execute(
            f"PRAGMA max_page_count={page_limit}"
        ).fetchone()[0])
        if configured > page_limit:
            raise RuntimeError("existing mint alert database exceeds byte limit")
        self.max_database_bytes = configured * page_size

    def _prune(self, database: sqlite3.Connection, now: datetime) -> None:
        cutoff = (now - self.retention).isoformat()
        database.execute(
            f"DELETE FROM {TABLE} WHERE delivered_at IS NOT NULL AND raised_at<?",
            (cutoff,),
        )
        excess = int(database.execute(
            f"SELECT MAX(0,COUNT(*)-?) FROM {TABLE}", (self.max_rows,)
        ).fetchone()[0])
        if excess:
            database.execute(
                f"DELETE FROM {TABLE} WHERE alert_id IN (SELECT alert_id FROM "
                f"{TABLE} WHERE delivered_at IS NOT NULL ORDER BY raised_at LIMIT ?)",
                (excess,),
            )
        total = int(database.execute(
            f"SELECT COUNT(*) FROM {TABLE}"
        ).fetchone()[0])
        if total > self.max_rows:
            raise RuntimeError("mint alert pending backlog exceeds its row limit")

    def _transaction(self):
        self._ensure_open()
        return immediate_transaction(
            self._connection, self._lock, lambda: secure_sqlite_files(self.path)
        )

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("mint alert store is closed")
