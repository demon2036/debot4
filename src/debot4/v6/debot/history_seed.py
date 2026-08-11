"""One-time import of previously observed DeBot ranks KOL increases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from ..identity import bsc_address, stable_id
from ..ledger import V6Ledger
from .ranks_poller import SOURCE


UTC = timezone.utc
QUERY = """
SELECT sequence, subject, available_at_us, dedupe_key, content_hash, payload_json
FROM events
WHERE source = 'debot' AND event_type = 'token_stage_snapshot'
  AND CAST(json_extract(payload_json, '$.kol_count_change.increase') AS INTEGER) > 0
ORDER BY sequence
"""


@dataclass(frozen=True, slots=True)
class SeedReport:
    scanned: int
    inserted: int
    replayed: int
    rejected: int


def seed_rank_history(database: str | Path, ledger: V6Ledger) -> SeedReport:
    source_path = Path(database).expanduser().resolve()
    if not source_path.is_file():
        return SeedReport(0, 0, 0, 0)
    connection = sqlite3.connect(f"{source_path.as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    scanned = inserted = replayed = rejected = 0
    try:
        for row in connection.execute(QUERY):
            scanned += 1
            parsed = _parse(row)
            if parsed is None:
                rejected += 1
                continue
            token, observed_at, sequence, metadata = parsed
            result = ledger.record_kol_evidence(
                evidence_id=stable_id(
                    "rank-kol-seed", sequence, metadata["legacy_content_hash"], token,
                ),
                chain="bsc", token_address=token,
                signal_id=f"rank-seed-{sequence}",
                event_at=observed_at, available_at=observed_at,
                qualified_at=observed_at, source=SOURCE,
                evidence_uri=f"https://debot.ai/token/bsc/{token}",
                metadata=metadata,
            )
            inserted += int(result.inserted)
            replayed += int(not result.inserted)
    finally:
        connection.close()
    return SeedReport(scanned, inserted, replayed, rejected)


def _parse(row: sqlite3.Row) -> tuple[str, datetime, int, dict[str, object]] | None:
    try:
        payload = json.loads(str(row["payload_json"]))
        token = bsc_address(row["subject"])
        if bsc_address(payload.get("token_address")) != token:
            return None
        change = payload["kol_count_change"]
        previous = int(change["previous"])
        current = int(change["current"])
        increase = int(change["increase"])
        available_us = int(row["available_at_us"])
        observed_at = datetime.fromtimestamp(available_us / 1_000_000, UTC)
        sequence = int(row["sequence"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if previous < 0 or current <= previous or increase != current - previous:
        return None
    return token, observed_at, sequence, {
        "schema": "debot_ranks_kol_seed.v1",
        "claim": "historical_kol_participation_proxy",
        "verification_level": "provider_aggregate_asserted",
        "chain_verified": False,
        "time_semantics": "legacy_client_fetch_completion",
        "previous_kols": previous,
        "current_kols": current,
        "increase": increase,
        "stage": str(payload.get("stage") or "unknown")[:32],
        "legacy_event_sequence": sequence,
        "legacy_dedupe_key": str(row["dedupe_key"])[:512],
        "legacy_content_hash": str(row["content_hash"]),
    }
