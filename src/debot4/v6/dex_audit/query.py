"""Read-only dashboard projection for the DEX coverage audit."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from typing import Any


UTC = timezone.utc


def audit_snapshot(database: str | Path, *, limit: int = 20) -> dict[str, Any]:
    path = Path(database)
    if not path.exists():
        return _empty("DEX audit database does not exist")
    try:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=2)
        connection.row_factory = sqlite3.Row
        try:
            latest = connection.execute(
                "SELECT * FROM dex_audit_runs ORDER BY as_of_us DESC, run_id DESC LIMIT 1"
            ).fetchone()
            if latest is None:
                return _empty(None)
            run_id = str(latest["run_id"])
            rows = connection.execute(
                "SELECT * FROM dex_audit_rows WHERE run_id=? ORDER BY rank LIMIT ?",
                (run_id, limit),
            ).fetchall()
            attempts = connection.execute(
                "SELECT * FROM dex_audit_attempts WHERE run_id=? ORDER BY attempt_no",
                (run_id,),
            ).fetchall()
            total_runs = int(
                connection.execute("SELECT COUNT(*) FROM dex_audit_runs").fetchone()[0]
            )
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return _empty(f"DEX audit read failed: {str(exc)[:160]}")
    discovered = sum(int(row["debot_discovered"]) for row in rows)
    decided = sum(int(row["debot_decided"]) for row in rows)
    bought = sum(int(row["debot_bought"]) for row in rows)
    count = len(rows)
    return {
        "available": True,
        "error": None,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {
            "total_runs": total_runs,
            "run_id": run_id,
            "as_of": _iso(int(latest["as_of_us"])),
            "source": latest["source"],
            "source_url": latest["source_url"],
            "universe": latest["universe"],
            "ranking_exact": bool(latest["ranking_exact"]),
            "success": bool(latest["success"]),
            "failure_reason": latest["failure_reason"],
            "ledger_available": bool(latest["ledger_available"]),
            "ledger_failure_reason": latest["ledger_failure_reason"],
            "row_count": int(latest["row_count"]),
            "displayed_count": count,
            "debot_discovered": discovered,
            "debot_decided": decided,
            "debot_bought": bought,
            "discovery_coverage_pct": _percent(discovered, count),
            "decision_coverage_pct": _percent(decided, count),
            "buy_coverage_pct": _percent(bought, count),
        },
        "rows": [_convert(row) for row in rows],
        "attempts": [_convert(row) for row in attempts],
    }


def _convert(row: sqlite3.Row) -> dict[str, Any]:
    converted: dict[str, Any] = {}
    booleans = {
        "success",
        "ranking_exact",
        "ledger_available",
        "debot_discovered",
        "debot_decided",
        "debot_bought",
    }
    for key in row.keys():
        value = row[key]
        if key.endswith("_at_us") or key in {"as_of_us", "started_at_us", "completed_at_us"}:
            converted[key.removesuffix("_us")] = None if value is None else _iso(int(value))
        elif key in booleans:
            converted[key] = bool(value)
        else:
            converted[key] = value
    return converted


def _iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1_000_000, UTC).isoformat()


def _percent(value: int, count: int) -> float | None:
    return None if count == 0 else round(value * 100 / count, 2)


def _empty(error: str | None) -> dict[str, Any]:
    return {
        "available": error is None,
        "error": error,
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": {},
        "rows": [],
        "attempts": [],
    }
