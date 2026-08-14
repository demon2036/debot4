"""Credential-free summaries of collector checkpoint files."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from .chain_mint_state import STATE_SCHEMA as CHAIN_MINT_STATE_SCHEMA
from .settings import NarrativeSettings


MAX_CHECKPOINT_BYTES = 2_000_000


@dataclass(frozen=True, slots=True)
class SourceCheckpointStatus:
    public: Mapping[str, Mapping[str, object]]
    x_latest_status_ids: Mapping[str, str]


def read_source_checkpoints(settings: NarrativeSettings) -> SourceCheckpointStatus:
    """Read bounded public counters without creating or mutating runtime state."""

    x_document, x_updated = _read_document(settings.x_checkpoint_path)
    debot_document, debot_updated = _read_document(settings.debot_checkpoint_path)
    telegram_document, telegram_updated = _read_document(
        settings.telegram_checkpoint_path
    )
    market_document, market_updated = _read_document(
        settings.market_checkpoint_path
    )
    chain_document, chain_updated = _read_document(
        settings.chain_mint_checkpoint_path
    )
    x_latest = _x_latest(x_document)
    telegram_channels = _mapping(telegram_document, "channels")
    seen_signals = _sequence(debot_document, "seen_signal_ids")
    emitted = _mapping(market_document, "emitted")
    chain_block = _chain_block(chain_document)
    public = {
        "x": {
            "available": x_document is not None,
            "checkpointed_accounts": len(x_latest),
            "accounts_with_latest_status": sum(bool(item) for item in x_latest.values()),
            "updated_at": x_updated,
        },
        "telegram": {
            "available": telegram_document is not None,
            "checkpointed_channels": len(telegram_channels),
            "channels_with_messages": sum(
                _positive_integer(value) for value in telegram_channels.values()
            ),
            "updated_at": telegram_updated,
        },
        "debot": {
            "available": debot_document is not None,
            "seen_signals": len(seen_signals),
            "updated_at": debot_updated,
        },
        "market": {
            "available": market_document is not None,
            "emitted_anomalies": len(emitted),
            "updated_at": market_updated,
        },
        "bsc_mints": {
            "available": chain_block is not None,
            "last_processed_block": chain_block,
            "finality": "included_not_finalized",
            "updated_at": chain_updated,
        },
    }
    return SourceCheckpointStatus(
        MappingProxyType({
            key: MappingProxyType(dict(value)) for key, value in public.items()
        }),
        MappingProxyType(x_latest),
    )


def _read_document(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        metadata = path.stat()
        if not path.is_file() or not 0 < metadata.st_size <= MAX_CHECKPOINT_BYTES:
            return None, None
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None, None
        updated = datetime.fromtimestamp(
            metadata.st_mtime, tz=timezone.utc
        ).isoformat()
        return raw, updated
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
        return None, None


def _x_latest(document: dict[str, Any] | None) -> dict[str, str]:
    accounts = _mapping(document, "accounts")
    latest: dict[str, str] = {}
    for key, value in accounts.items():
        if not isinstance(key, str) or not isinstance(value, dict):
            continue
        handle = str(value.get("handle", key)).strip().lstrip("@").casefold()
        tweet_id = str(value.get("latest_tweet_id", "")).strip()
        if handle and (not tweet_id or tweet_id.isdigit()):
            latest[handle] = tweet_id
    return latest


def _mapping(
    document: dict[str, Any] | None, key: str
) -> Mapping[str, Any]:
    if document is None:
        return {}
    value = document.get(key)
    return value if isinstance(value, dict) and len(value) <= 20_000 else {}


def _sequence(document: dict[str, Any] | None, key: str) -> tuple[object, ...]:
    if document is None:
        return ()
    value = document.get(key)
    if not isinstance(value, list) or len(value) > 100_000:
        return ()
    return tuple(value)


def _positive_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _chain_block(document: dict[str, Any] | None) -> int | None:
    if document is None or document.get("schema") != CHAIN_MINT_STATE_SCHEMA:
        return None
    value = document.get("block_number")
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value
