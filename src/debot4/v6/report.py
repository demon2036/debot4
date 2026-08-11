"""Read-only dashboard projections from the append-only ledger."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import json
import sqlite3
from typing import Any


UTC = timezone.utc


def ledger_snapshot(database: str | Path, *, limit: int = 40) -> dict[str, Any]:
    path = Path(database)
    if not path.exists():
        return _empty()
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
    connection.row_factory = sqlite3.Row
    try:
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "summary": _summary(connection),
            "buys": _buys(connection, limit),
            "decisions": _decisions(connection, limit),
            "signals": _signals(connection, limit),
        }
    finally:
        connection.close()


def _summary(db: sqlite3.Connection) -> dict[str, Any]:
    count = lambda table: int(db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    statuses = {
        str(row[0]): int(row[1])
        for row in db.execute(
            "SELECT status, COUNT(*) FROM v6_entry_decisions GROUP BY status"
        )
    }
    outcome_rows = db.execute(
        "SELECT status, final_pnl_usd, peak_multiple FROM v6_one_hour_results"
    ).fetchall()
    complete = [row for row in outcome_rows if row[0] == "complete"]
    profits = [_decimal(row[1]) for row in complete if row[1] is not None]
    peaks = [_decimal(row[2]) for row in complete if row[2] is not None]
    return {
        "signals": count("v6_current_signals"),
        "historical_kol": count("v6_kol_evidence"),
        "decisions": count("v6_entry_decisions"),
        "buys": count("v6_simulated_buys"),
        "observations": count("v6_block_observations"),
        "outcomes_complete": len(complete),
        "outcomes_incomplete": len(outcome_rows) - len(complete),
        "decision_statuses": statuses,
        "profitable_1h": sum(value > 0 for value in profits),
        "mean_final_pnl_usd": _mean(profits),
        "median_peak_multiple": _median(peaks),
    }


def _buys(db: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT b.*, d.reason AS decision_reason, r.status AS outcome_status, "
        "r.peak_fdv_usd, r.final_fdv_usd, r.peak_multiple, r.final_multiple, "
        "r.peak_pnl_usd, r.final_pnl_usd, "
        "(SELECT o.fdv_usd FROM v6_block_observations o WHERE o.buy_id=b.buy_id "
        " ORDER BY o.observed_at_us DESC LIMIT 1) AS latest_fdv_usd, "
        "(SELECT o.position_value_usd FROM v6_block_observations o "
        " WHERE o.buy_id=b.buy_id ORDER BY o.observed_at_us DESC LIMIT 1) "
        "AS latest_position_value_usd FROM v6_simulated_buys b "
        "JOIN v6_entry_decisions d ON d.decision_id=b.decision_id "
        "LEFT JOIN v6_one_hour_results r ON r.buy_id=b.buy_id "
        "ORDER BY b.executed_at_us DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row(row) for row in rows]


def _decisions(db: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT d.*, s.token_address, s.signal_kind, s.event_at_us, "
        "s.metadata_json AS signal_metadata_json FROM v6_entry_decisions d "
        "JOIN v6_current_signals s ON s.signal_id=d.signal_id "
        "ORDER BY d.decided_at_us DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row(row) for row in rows]


def _signals(db: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        "SELECT * FROM v6_current_signals ORDER BY event_at_us DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [_row(row) for row in rows]


def _row(row: sqlite3.Row) -> dict[str, Any]:
    result = {}
    for key in row.keys():
        value = row[key]
        if key.endswith("_us") and isinstance(value, int):
            result[key[:-3] + "_at"] = datetime.fromtimestamp(
                value / 1_000_000, UTC
            ).isoformat()
        elif key.endswith("metadata_json") and isinstance(value, str):
            try:
                result[key[:-5]] = json.loads(value)
            except ValueError:
                result[key[:-5]] = {}
        else:
            result[key] = value
    return result


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(0)


def _mean(values: list[Decimal]) -> str | None:
    return None if not values else format(sum(values) / len(values), ".6f")


def _median(values: list[Decimal]) -> str | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    value = ordered[middle] if len(ordered) % 2 else (
        ordered[middle - 1] + ordered[middle]
    ) / 2
    return format(value, ".6f")


def _empty() -> dict[str, Any]:
    return {"generated_at": datetime.now(UTC).isoformat(), "summary": {}, "buys": [], "decisions": [], "signals": []}
