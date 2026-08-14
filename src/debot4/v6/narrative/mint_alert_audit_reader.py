"""Read-only SQLite adapters for the periodic mint-alert audit."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sqlite3

from ..identity import bsc_address, utc_datetime
from .mint_alert_audit_models import DeBotMintSeen, StoredMintAlert
from .mint_alert_store import TABLE as ALERT_TABLE
from .mint_alert_store_codec import alert_from_row
from .mint_location import DEBOT_STAGE_SOURCES
from .mint_location_store import TABLE as LOCATION_TABLE


class MintAlertAuditReadError(RuntimeError):
    """An audit input is missing, oversized, or unreadable."""


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
    path: str | Path, *, since: datetime, limit: int = 5_000,
) -> tuple[DeBotMintSeen, ...]:
    _validate_limit(limit)
    database = _connect(path, "mint location database")
    stage_sources = tuple(sorted(DEBOT_STAGE_SOURCES.values()))
    placeholders = ",".join("?" for _ in stage_sources)
    parameters = (*stage_sources, utc_datetime(since).isoformat())
    try:
        rows = database.execute(
            f"SELECT exact_ca,source,first_observed_at,last_observed_at "
            f"FROM {LOCATION_TABLE} WHERE source IN ({placeholders}) "
            "AND last_observed_at>=? ORDER BY last_observed_at DESC LIMIT ?",
            (*parameters, limit + 1),
        ).fetchall()
        if len(rows) > limit:
            raise MintAlertAuditReadError("DeBot mint audit row limit exceeded")
        grouped: dict[str, tuple[datetime, datetime, set[str]]] = {}
        for row in rows:
            exact_ca = bsc_address(row["exact_ca"])
            first = utc_datetime(datetime.fromisoformat(row["first_observed_at"]))
            last = utc_datetime(datetime.fromisoformat(row["last_observed_at"]))
            source = str(row["source"])
            previous = grouped.get(exact_ca)
            if previous is None:
                grouped[exact_ca] = (first, last, {source})
            else:
                grouped[exact_ca] = (
                    min(previous[0], first), max(previous[1], last),
                    previous[2] | {source},
                )
        return tuple(
            DeBotMintSeen(exact_ca, first, last, tuple(sources))
            for exact_ca, (first, last, sources) in sorted(grouped.items())
        )
    except MintAlertAuditReadError:
        raise
    except (sqlite3.Error, TypeError, ValueError) as exc:
        raise MintAlertAuditReadError("cannot read mint location database") from exc
    finally:
        database.close()


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


__all__ = ["MintAlertAuditReadError", "read_debot_mints", "read_mint_alerts"]
