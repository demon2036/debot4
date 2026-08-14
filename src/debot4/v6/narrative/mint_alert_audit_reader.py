"""Read-only SQLite adapters for the periodic mint-alert audit."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import math
from pathlib import Path
import sqlite3
from time import monotonic, sleep

from ..identity import bsc_address, utc_datetime
from .mint_alert_audit_models import DeBotMintSeen, StoredMintAlert
from .mint_alert_gate_codec import (
    MintAlertGateState,
    read_mint_alert_gate_state,
)
from .mint_alert_store import TABLE as ALERT_TABLE
from .mint_alert_store_codec import alert_from_row
from .mint_location import DEBOT_STAGE_SOURCES
from .mint_location_store import TABLE as LOCATION_TABLE


class MintAlertAuditReadError(RuntimeError):
    """An audit input is missing, oversized, or unreadable."""


@dataclass(frozen=True, slots=True)
class MintAlertAuditInputs:
    gate: MintAlertGateState
    alerts: tuple[StoredMintAlert, ...]
    debot_mints: tuple[DeBotMintSeen, ...]
    debot_exact_ca_count: int


def wait_for_mint_alert_audit_inputs(
    gate_path: str | Path,
    alert_path: str | Path,
    location_path: str | Path,
    *,
    now: datetime,
    debot_exact_cas: tuple[str, ...] | None = None,
    timeout_seconds: float = 15.0,
    poll_seconds: float = 0.1,
    monotonic_clock: Callable[[], float] = monotonic,
    sleeper: Callable[[float], None] = sleep,
) -> MintAlertAuditInputs:
    """Wait briefly for runtime-owned state before failing the audit closed."""

    if (
        not math.isfinite(timeout_seconds)
        or not math.isfinite(poll_seconds)
        or timeout_seconds <= 0
        or poll_seconds <= 0
    ):
        raise ValueError("audit readiness intervals must be positive and finite")
    deadline = monotonic_clock() + timeout_seconds
    last_error: MintAlertAuditReadError | None = None
    while True:
        try:
            gate = read_mint_alert_gate_state(gate_path)
            if gate is None:
                raise MintAlertAuditReadError(
                    "mint alert gate state is unavailable"
                )
            current = utc_datetime(now)
            since = max(gate.policy_started_at, current - timedelta(days=1))
            alerts = read_mint_alerts(alert_path, since=since)
            debot_exact_ca_count = count_debot_exact_cas(
                location_path, since=since
            )
            debot_mints = read_debot_mints(
                location_path, since=since, exact_cas=debot_exact_cas
            )
            return MintAlertAuditInputs(
                gate, alerts, debot_mints, debot_exact_ca_count
            )
        except MintAlertAuditReadError as exc:
            last_error = exc
        remaining = deadline - monotonic_clock()
        if remaining <= 0:
            assert last_error is not None
            raise last_error
        sleeper(min(poll_seconds, remaining))


def read_mint_alerts(
    path: str | Path, *, since: datetime, limit: int = 5_000,
) -> tuple[StoredMintAlert, ...]:
    _validate_limit(limit)
    database = _connect(path, "mint alert database")
    try:
        rows = database.execute(
            f"SELECT * FROM {ALERT_TABLE} WHERE raised_at>=? "
            "ORDER BY raised_at DESC,alert_id DESC LIMIT ?",
            (utc_datetime(since).isoformat(), limit + 1),
        ).fetchall()
        if len(rows) > limit:
            raise MintAlertAuditReadError("mint alert audit row limit exceeded")
        return tuple(
            StoredMintAlert(
                alert_from_row(row),
                None if row["delivered_at"] is None else utc_datetime(
                    datetime.fromisoformat(row["delivered_at"])
                ),
            )
            for row in rows
        )
    except MintAlertAuditReadError:
        raise
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise MintAlertAuditReadError("cannot read mint alert database") from exc
    finally:
        database.close()


def read_debot_mints(
    path: str | Path,
    *,
    since: datetime,
    exact_cas: tuple[str, ...] | None = None,
    limit: int = 5_000,
) -> tuple[DeBotMintSeen, ...]:
    _validate_limit(limit)
    addresses = (
        None
        if exact_cas is None
        else tuple(dict.fromkeys(bsc_address(item) for item in exact_cas))
    )
    database = _connect(path, "mint location database")
    try:
        if addresses == ():
            return ()
        where, parameters = _debot_where(since, addresses)
        rows = database.execute(
            f"SELECT exact_ca,MIN(first_observed_at) AS first_observed_at,"
            "MAX(last_observed_at) AS last_observed_at,"
            f"GROUP_CONCAT(DISTINCT source) AS sources FROM {LOCATION_TABLE} "
            f"WHERE {where} GROUP BY exact_ca "
            "ORDER BY last_observed_at DESC,exact_ca LIMIT ?",
            (*parameters, limit + 1),
        ).fetchall()
        if len(rows) > limit:
            raise MintAlertAuditReadError("DeBot mint audit row limit exceeded")
        return tuple(
            DeBotMintSeen(
                row["exact_ca"],
                datetime.fromisoformat(row["first_observed_at"]),
                datetime.fromisoformat(row["last_observed_at"]),
                tuple(str(row["sources"]).split(",")),
            )
            for row in rows
        )
    except MintAlertAuditReadError:
        raise
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise MintAlertAuditReadError("cannot read mint location database") from exc
    finally:
        database.close()


def count_debot_exact_cas(
    path: str | Path, *, since: datetime,
) -> int:
    database = _connect(path, "mint location database")
    try:
        where, parameters = _debot_where(since, None)
        row = database.execute(
            f"SELECT COUNT(DISTINCT exact_ca) FROM {LOCATION_TABLE} WHERE {where}",
            parameters,
        ).fetchone()
        return int(row[0])
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise MintAlertAuditReadError("cannot count DeBot mint locations") from exc
    finally:
        database.close()


def _debot_where(
    since: datetime, exact_cas: tuple[str, ...] | None,
) -> tuple[str, tuple[object, ...]]:
    stage_sources = tuple(sorted(DEBOT_STAGE_SOURCES.values()))
    source_marks = ",".join("?" for _ in stage_sources)
    clauses = [f"source IN ({source_marks})", "last_observed_at>=?"]
    parameters: list[object] = [
        *stage_sources, utc_datetime(since).isoformat()
    ]
    if exact_cas is not None:
        clauses.append("exact_ca IN (" + ",".join("?" for _ in exact_cas) + ")")
        parameters.extend(exact_cas)
    return " AND ".join(clauses), tuple(parameters)


def _connect(path: str | Path, label: str) -> sqlite3.Connection:
    target = Path(path)
    if target.is_symlink() or not target.is_file():
        raise MintAlertAuditReadError(f"{label} is not a regular file")
    database: sqlite3.Connection | None = None
    try:
        database = sqlite3.connect(
            f"{target.resolve().as_uri()}?mode=ro", uri=True, timeout=1
        )
        database.row_factory = sqlite3.Row
        database.execute("PRAGMA query_only=ON")
        return database
    except (OSError, sqlite3.Error) as exc:
        if database is not None:
            database.close()
        raise MintAlertAuditReadError(f"cannot open {label}") from exc


def _validate_limit(limit: int) -> None:
    if isinstance(limit, bool) or not 1 <= limit <= 20_000:
        raise ValueError("mint alert audit limit must be between 1 and 20000")


__all__ = [
    "MintAlertAuditInputs",
    "MintAlertAuditReadError",
    "count_debot_exact_cas",
    "read_debot_mints",
    "read_mint_alerts",
    "wait_for_mint_alert_audit_inputs",
]
