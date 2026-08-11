"""Independent append-only SQLite writer for DEX audit runs."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3

from .models import Board, CoverageBatch, StoredRun
from .schema import install_schema


UTC = timezone.utc


def _now_us() -> int:
    return int(datetime.now(UTC).timestamp() * 1_000_000)


class AuditStore:
    def __init__(
        self,
        database: str | Path,
        *,
        clock_us: Callable[[], int] = _now_us,
    ) -> None:
        self.path = Path(database)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._clock_us = clock_us
        self._connection = sqlite3.connect(
            self.path, isolation_level=None, timeout=5, check_same_thread=False
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        install_schema(self._connection)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> AuditStore:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def append(
        self, *, run_id: str, board: Board, coverage: CoverageBatch
    ) -> StoredRun:
        if len(board.rows) != len(coverage.rows):
            raise ValueError("coverage row count does not match board")
        for gain, match in zip(board.rows, coverage.rows, strict=True):
            if gain.token_address != match.token_address:
                raise ValueError("coverage token order does not match board")
        db = self._connection
        db.execute("BEGIN IMMEDIATE")
        try:
            db.execute(
                "INSERT INTO dex_audit_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    run_id,
                    board.as_of_us,
                    board.source,
                    board.source_url,
                    board.universe,
                    int(board.ranking_exact),
                    int(board.success),
                    board.failure_reason,
                    int(coverage.available),
                    coverage.failure_reason,
                    len(board.rows),
                    self._clock_us(),
                ),
            )
            for number, attempt in enumerate(board.attempts, 1):
                db.execute(
                    "INSERT INTO dex_audit_attempts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        run_id,
                        number,
                        attempt.source,
                        attempt.method,
                        attempt.url,
                        attempt.request_json,
                        attempt.started_at_us,
                        attempt.completed_at_us,
                        attempt.latency_ms,
                        attempt.http_status,
                        attempt.response_bytes,
                        int(attempt.success),
                        attempt.failure_reason,
                    ),
                )
            for rank, (gain, match) in enumerate(
                zip(board.rows, coverage.rows, strict=True), 1
            ):
                db.execute(
                    "INSERT INTO dex_audit_rows VALUES ("
                    + ",".join("?" for _ in range(27))
                    + ")",
                    (
                        run_id,
                        rank,
                        board.as_of_us,
                        board.source,
                        board.source_url,
                        gain.token_address,
                        gain.pair_address,
                        gain.symbol,
                        gain.name,
                        _text(gain.h1_change_pct),
                        _text(gain.liquidity_usd),
                        _text(gain.fdv_usd),
                        _text(gain.market_cap_usd),
                        _text(gain.price_usd),
                        _text(gain.volume_h1_usd),
                        gain.txns_h1,
                        int(match.discovered),
                        match.signal_id,
                        match.signal_at_us,
                        int(match.decided),
                        match.decision_id,
                        match.decision_at_us,
                        match.decision_status,
                        int(match.bought),
                        match.buy_id,
                        match.buy_at_us,
                        match.miss_reason,
                    ),
                )
            db.execute("COMMIT")
        except BaseException:
            db.execute("ROLLBACK")
            raise
        return StoredRun(
            run_id=run_id,
            as_of_us=board.as_of_us,
            source=board.source,
            row_count=len(board.rows),
            success=board.success,
        )


def _text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
