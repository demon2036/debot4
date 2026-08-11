"""Connection, transaction, and immutable insert primitives."""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, TypeVar

from .codec import V6LedgerConflict, to_us
from .models import InsertResult
from .schema import install_schema


T = TypeVar("T")
UTC = timezone.utc


class LedgerCore:
    """Small file-backed SQLite core shared by the v6 ledger mixins."""

    def __init__(
        self,
        database: str | os.PathLike[str],
        *,
        timeout_seconds: float = 5.0,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        name = os.fspath(database)
        if name == ":memory:" or "mode=memory" in name:
            raise ValueError("a file-backed database is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        Path(name).parent.mkdir(parents=True, exist_ok=True)
        self._clock = clock
        self._lock = RLock()
        self._depth = 0
        self._rollback_only = False
        self._transaction_commit_seq: int | None = None
        self._transaction_now_us: int | None = None
        self._closed = False
        self._connection = sqlite3.connect(
            name,
            timeout=timeout_seconds,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = NORMAL")
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.execute("PRAGMA recursive_triggers = ON")
            self._connection.execute(
                f"PRAGMA busy_timeout = {int(timeout_seconds * 1_000)}"
            )
            install_schema(self._connection)
        except BaseException:
            self._connection.close()
            self._closed = True
            raise

    def __enter__(self):
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self._connection.close()
                self._closed = True

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("ledger is closed")

    def _now_us(self) -> int:
        if self._transaction_now_us is not None:
            return self._transaction_now_us
        return to_us(self._clock(), "clock result")

    @contextmanager
    def _read(self) -> Iterator[None]:
        with self._lock:
            self._ensure_open()
            yield

    @contextmanager
    def _write(self) -> Iterator[None]:
        with self._lock:
            self._ensure_open()
            outer = self._depth == 0
            if outer:
                self._connection.execute("BEGIN IMMEDIATE")
                self._rollback_only = False
                try:
                    raw_us = to_us(self._clock(), "clock result")
                    row = self._connection.execute(
                        "SELECT MAX(committed_at_us) FROM v6_commits"
                    ).fetchone()
                    previous_us = None if row is None else row[0]
                    committed_at_us = (
                        raw_us if previous_us is None
                        else max(raw_us, int(previous_us) + 1)
                    )
                    cursor = self._connection.execute(
                        "INSERT INTO v6_commits(committed_at_us) VALUES (?)",
                        (committed_at_us,),
                    )
                    self._transaction_commit_seq = int(cursor.lastrowid)
                    self._transaction_now_us = committed_at_us
                except BaseException:
                    self._connection.execute("ROLLBACK")
                    raise
            self._depth += 1
            try:
                yield
            except BaseException:
                self._rollback_only = True
                raise
            finally:
                self._depth -= 1
                if outer:
                    try:
                        statement = "ROLLBACK" if self._rollback_only else "COMMIT"
                        self._connection.execute(statement)
                    except BaseException:
                        if self._connection.in_transaction:
                            self._connection.execute("ROLLBACK")
                        raise
                    finally:
                        self._rollback_only = False
                        self._transaction_commit_seq = None
                        self._transaction_now_us = None

    def _append(
        self,
        *,
        table: str,
        key_column: str,
        key_value: str,
        columns: Sequence[str],
        values: Sequence[object],
        label: str,
        decode: Callable[[sqlite3.Row], T],
    ) -> InsertResult[T]:
        with self._write():
            assert self._transaction_commit_seq is not None
            commit_seq = self._transaction_commit_seq
            inserted_at_us = self._now_us()
            existing = self._connection.execute(
                f"SELECT * FROM {table} WHERE {key_column} = ?", (key_value,)
            ).fetchone()
            if existing is not None:
                actual = tuple(existing[column] for column in columns)
                if actual != tuple(values):
                    raise V6LedgerConflict(
                        f"{label} {key_value!r} already has different content"
                    )
                return InsertResult(decode(existing), False)
            all_columns = (*columns, "commit_seq", "inserted_at_us")
            placeholders = ", ".join("?" for _ in all_columns)
            self._connection.execute(
                f"INSERT INTO {table} ({', '.join(all_columns)}) "
                f"VALUES ({placeholders})",
                (*values, commit_seq, inserted_at_us),
            )
            row = self._connection.execute(
                f"SELECT * FROM {table} WHERE {key_column} = ?", (key_value,)
            ).fetchone()
        assert row is not None
        return InsertResult(decode(row), True)

    def _row(self, sql: str, values: Sequence[object]) -> sqlite3.Row | None:
        with self._read():
            return self._connection.execute(sql, tuple(values)).fetchone()

    def _rows(self, sql: str, values: Sequence[object]) -> list[sqlite3.Row]:
        with self._read():
            return self._connection.execute(sql, tuple(values)).fetchall()
