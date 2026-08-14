"""Credential-free, read-only summary of durable Exact CA evidence."""

from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

from .mint_location import MINT_LOCATION_SOURCES
from .mint_location_store import TABLE


def read_mint_location_status(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "observations": 0,
        "unique_exact_cas": 0,
        "by_source": {key: 0 for key in sorted(MINT_LOCATION_SOURCES)},
        "last_observed_at": None,
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
            row = database.execute(
                f"SELECT COUNT(*) observations,COUNT(DISTINCT exact_ca) cas,"
                f"MAX(last_observed_at) latest FROM {TABLE}"
            ).fetchone()
            sources = database.execute(
                f"SELECT source,COUNT(*) total FROM {TABLE} GROUP BY source"
            ).fetchall()
        finally:
            database.close()
    except (OSError, sqlite3.Error):
        return result
    result.update({
        "available": True,
        "observations": int(row["observations"]),
        "unique_exact_cas": int(row["cas"]),
        "last_observed_at": row["latest"],
    })
    result["by_source"].update({
        str(item["source"]): int(item["total"]) for item in sources
    })
    return result
