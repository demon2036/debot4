"""Bounded SQLite evidence store for every independently located exact CA."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sqlite3
from threading import RLock

from ..identity import utc_datetime, utc_now
from .job_queue_sqlite import (
    immediate_transaction,
    prepare_private_database,
    secure_sqlite_files,
)
from .mint_location import MINT_LOCATION_SOURCES, MintLocation
from .mint_location_codec import (
    MintLocationConflict,
    insert_values,
    location_from_row,
    merge_values,
)


TABLE = "mint_locations"
DEFAULT_MAX_DATABASE_BYTES = 64 * 1_024 * 1_024
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    location_id TEXT PRIMARY KEY,
    exact_ca TEXT NOT NULL,
    source TEXT NOT NULL,
    first_observed_at TEXT NOT NULL,
    last_observed_at TEXT NOT NULL,
    created_at TEXT,
    launchpad TEXT,
    token_name TEXT,
    token_symbol TEXT,
    provider_fdv_usd TEXT,
    social_urls_json TEXT NOT NULL,
    transaction_hash TEXT,
    block_number INTEGER,
    block_hash TEXT,
    transaction_index INTEGER,
    factory_address TEXT,
    authorizes_trade INTEGER NOT NULL DEFAULT 0 CHECK(authorizes_trade = 0)
);
CREATE INDEX IF NOT EXISTS mint_locations_ca_idx
ON {TABLE}(exact_ca, first_observed_at);
CREATE INDEX IF NOT EXISTS mint_locations_last_seen_idx
ON {TABLE}(last_observed_at, location_id);
PRAGMA user_version=1;
"""


@dataclass(frozen=True, slots=True)
class MintLocationWrite:
    inserted: int = 0
    enriched: int = 0
    unchanged: int = 0


class MintLocationStore:
    def __init__(
        self,
        database: str | Path,
        *,
        clock=utc_now,
        retention: timedelta = timedelta(days=1),
        max_rows: int = 20_000,
        max_database_bytes: int = DEFAULT_MAX_DATABASE_BYTES,
    ) -> None:
        if not timedelta(minutes=15) <= retention <= timedelta(days=7):
            raise ValueError("mint retention must be between 15 minutes and 7 days")
        if isinstance(max_rows, bool) or not 100 <= max_rows <= 100_000:
            raise ValueError("mint location row limit must be between 100 and 100000")
        if (
            isinstance(max_database_bytes, bool)
            or not 8 * 1_024 * 1_024
            <= max_database_bytes <= 256 * 1_024 * 1_024
        ):
            raise ValueError("mint location database byte limit is invalid")
        self.path = Path(database)
        if str(database) == ":memory:" or str(database).startswith("file:"):
            raise ValueError("mint locations require a file-backed database")
        prepare_private_database(self.path)
        self.clock = clock
        self.retention = retention
        self.max_rows = max_rows
        self.max_database_bytes = int(max_database_bytes)
        self._lock = RLock()
        self._closed = False
        self._next_prune_at: datetime | None = None
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

    def __enter__(self) -> "MintLocationStore":
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def record(self, locations: Iterable[MintLocation]) -> MintLocationWrite:
        items = tuple(locations)
        if not items:
            return MintLocationWrite()
        if len(items) > 1_000:
            raise ValueError("too many mint locations in one write")
        inserted = enriched = unchanged = 0
        now = utc_datetime(self.clock())
        prune = self._reserve_prune(now)
        with self._transaction() as database:
            for item in items:
                row = database.execute(
                    f"SELECT * FROM {TABLE} WHERE location_id=?",
                    (item.location_id,),
                ).fetchone()
                if row is None:
                    database.execute(
                        f"INSERT INTO {TABLE} VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0)",
                        insert_values(item),
                    )
                    inserted += 1
                    continue
                values = merge_values(row, item)
                if values is None:
                    unchanged += 1
                    continue
                database.execute(
                    f"UPDATE {TABLE} SET first_observed_at=?,last_observed_at=?,"
                    "created_at=?,launchpad=?,token_name=?,token_symbol=?,"
                    "provider_fdv_usd=?,social_urls_json=? WHERE location_id=?",
                    (*values, item.location_id),
                )
                enriched += 1
            if prune:
                self._prune(database, now)
        return MintLocationWrite(inserted, enriched, unchanged)

    def recent(
        self, start: datetime, end: datetime, *, limit: int = 200
    ) -> tuple[MintLocation, ...]:
        lower, upper = utc_datetime(start), utc_datetime(end)
        if lower > upper or isinstance(limit, bool) or not 1 <= limit <= 1_000:
            raise ValueError("invalid mint location query window")
        with self._lock:
            self._ensure_open()
            rows = self._connection.execute(
                f"SELECT * FROM {TABLE} WHERE "
                "COALESCE(created_at,first_observed_at) BETWEEN ? AND ? "
                "ORDER BY COALESCE(created_at,first_observed_at),"
                "first_observed_at,location_id LIMIT ?",
                (lower.isoformat(), upper.isoformat(), limit),
            ).fetchall()
        return tuple(location_from_row(row) for row in rows)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            self._ensure_open()
            total = int(self._connection.execute(
                f"SELECT COUNT(*) FROM {TABLE}"
            ).fetchone()[0])
            unique = int(self._connection.execute(
                f"SELECT COUNT(DISTINCT exact_ca) FROM {TABLE}"
            ).fetchone()[0])
            rows = self._connection.execute(
                f"SELECT source,COUNT(*) FROM {TABLE} GROUP BY source"
            ).fetchall()
            latest = self._connection.execute(
                f"SELECT MAX(last_observed_at) FROM {TABLE}"
            ).fetchone()[0]
        counts = {source: 0 for source in sorted(MINT_LOCATION_SOURCES)}
        counts.update({str(row[0]): int(row[1]) for row in rows})
        return {
            "observations": total,
            "unique_exact_cas": unique,
            "by_source": counts,
            "last_observed_at": latest,
            "max_rows": self.max_rows,
            "max_database_bytes": self.max_database_bytes,
            "authorizes_trade": False,
        }

    def _apply_page_limit(self) -> None:
        page_size = int(self._connection.execute(
            "PRAGMA page_size"
        ).fetchone()[0])
        page_limit = self.max_database_bytes // page_size
        configured = int(self._connection.execute(
            f"PRAGMA max_page_count={page_limit}"
        ).fetchone()[0])
        if configured > page_limit:
            raise RuntimeError("existing mint location database exceeds byte limit")
        self.max_database_bytes = configured * page_size

    def _prune(self, database: sqlite3.Connection, now: datetime) -> None:
        cutoff = (now - self.retention).isoformat()
        database.execute(
            f"DELETE FROM {TABLE} WHERE last_observed_at < ?", (cutoff,)
        )
        excess = int(database.execute(
            f"SELECT MAX(0,COUNT(*)-?) FROM {TABLE}", (self.max_rows,)
        ).fetchone()[0])
        if excess:
            database.execute(
                f"DELETE FROM {TABLE} WHERE location_id IN (SELECT location_id "
                f"FROM {TABLE} ORDER BY last_observed_at,location_id LIMIT ?)",
                (excess,),
            )

    def _transaction(self):
        self._ensure_open()
        return immediate_transaction(
            self._connection, self._lock, lambda: secure_sqlite_files(self.path)
        )

    def _reserve_prune(self, now: datetime) -> bool:
        with self._lock:
            self._ensure_open()
            if self._next_prune_at is not None and now < self._next_prune_at:
                return False
            self._next_prune_at = now + timedelta(minutes=1)
            return True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("mint location store is closed")
