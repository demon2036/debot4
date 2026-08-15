"""Credential-free read-only status for accepted tweet-to-mint alerts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3
from typing import Any

from .mint_alert import MINT_ALERT_DECISION_REASON, MINT_ALERT_SLA_SECONDS
from .mint_alert_store import TABLE


def read_mint_alert_status(path: Path, *, limit: int = 20) -> dict[str, Any]:
    if isinstance(limit, bool) or not 1 <= limit <= 100:
        raise ValueError("mint alert status limit must be between 1 and 100")
    result: dict[str, Any] = {
        "available": False,
        "total": 0,
        "pending_delivery": 0,
        "delivered": 0,
        "detection_sla_met": 0,
        "delivery_sla_met": 0,
        "last_raised_at": None,
        "recent_alerts": [],
        "sla_seconds": MINT_ALERT_SLA_SECONDS,
        "trigger": MINT_ALERT_DECISION_REASON,
        "raw_mint_triggers_alert": False,
        "rpc_on_critical_path": False,
        "model_on_critical_path": True,
        "authorizes_trade": False,
    }
    if not path.is_file():
        return result
    try:
        database = sqlite3.connect(
            f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=1
        )
        database.row_factory = sqlite3.Row
        try:
            database.execute("PRAGMA query_only=ON")
            totals = database.execute(_totals_sql()).fetchone()
            rows = database.execute(
                f"SELECT * FROM {TABLE} "
                "ORDER BY raised_at DESC,alert_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        finally:
            database.close()
        recent = [_public_row(row) for row in rows]
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return result
    result.update({
        "available": True,
        "total": int(totals["total"] or 0),
        "pending_delivery": int(totals["pending"] or 0),
        "delivered": int(totals["delivered"] or 0),
        "detection_sla_met": int(totals["detected_fast"] or 0),
        "delivery_sla_met": int(totals["delivered_fast"] or 0),
        "last_raised_at": totals["latest"],
        "recent_alerts": recent,
    })
    return result


def _totals_sql() -> str:
    return (
        f"SELECT COUNT(*) total,"
        "SUM(CASE WHEN delivered_at IS NULL THEN 1 ELSE 0 END) pending,"
        "SUM(CASE WHEN delivered_at IS NOT NULL THEN 1 ELSE 0 END) delivered,"
        "SUM(CASE WHEN (julianday(raised_at)-julianday(catalyst_created_at))"
        f"*86400<={MINT_ALERT_SLA_SECONDS + 0.001} THEN 1 ELSE 0 END) detected_fast,"
        "SUM(CASE WHEN delivered_at IS NOT NULL AND "
        "(julianday(delivered_at)-julianday(catalyst_created_at))*86400"
        f"<={MINT_ALERT_SLA_SECONDS + 0.001} THEN 1 ELSE 0 END) delivered_fast,"
        f"MAX(raised_at) latest FROM {TABLE}"
    )


def _public_row(row: sqlite3.Row) -> dict[str, object]:
    catalyst_at = datetime.fromisoformat(row["catalyst_created_at"])
    raised_at = datetime.fromisoformat(row["raised_at"])
    delivered_at = (
        None
        if row["delivered_at"] is None
        else datetime.fromisoformat(row["delivered_at"])
    )
    detection = max(0.0, (raised_at - catalyst_at).total_seconds())
    delivery = (
        None
        if delivered_at is None
        else max(0.0, (delivered_at - catalyst_at).total_seconds())
    )
    return {
        "alert_id": row["alert_id"],
        "exact_ca": row["exact_ca"],
        "token_name": row["token_name"],
        "token_symbol": row["token_symbol"],
        "token_stage": row["token_stage"],
        "launchpad": row["launchpad"],
        "match_kind": row["match_kind"],
        "catalyst_tweet_id": row["catalyst_tweet_id"],
        "catalyst_author": row["catalyst_author"],
        "catalyst_text": row["catalyst_text"],
        "catalyst_status_url": row["token_status_url"],
        "catalyst_created_at": row["catalyst_created_at"],
        "token_created_at": row["token_created_at"],
        "match_observed_at": row["match_observed_at"],
        "raised_at": row["raised_at"],
        "decision_reason": row["decision_reason"],
        "qualification_model": row["qualification_model"],
        "qualified_at": row["qualified_at"],
        "delivered_at": row["delivered_at"],
        "delivery_status": "pending" if delivered_at is None else "delivered",
        "delivery_attempts": int(row["delivery_attempts"]),
        "last_delivery_error_type": row["last_delivery_error_type"],
        "detection_latency_seconds": detection,
        "delivery_latency_seconds": delivery,
        "within_detection_sla": detection <= MINT_ALERT_SLA_SECONDS,
        "within_delivery_sla": (
            None if delivery is None else delivery <= MINT_ALERT_SLA_SECONDS
        ),
        "triggered_by_raw_mint": False,
        "rpc_on_critical_path": False,
        "model_on_critical_path": row["qualification_model"] is not None,
        "authorizes_trade": False,
    }
