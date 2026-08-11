"""Canonical validation and SQLite encoding helpers for the v6 ledger."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re


UTC = timezone.utc
ONE_HOUR = timedelta(hours=1)
ONE_HOUR_US = 3_600_000_000
OFFICIAL_KOL_SOURCE = "debot:bsc:official-signal"
RANKS_KOL_SOURCE = "debot:bsc:ranks-kol-increase"
KOL_SOURCES = frozenset((OFFICIAL_KOL_SOURCE, RANKS_KOL_SOURCE))
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_EVM_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_BLOCK_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")


class V6LedgerConflict(RuntimeError):
    """An immutable ledger identity was replayed with different content."""


class V6LedgerFinalized(RuntimeError):
    """A new observation was attempted after its one-hour result was sealed."""


def text(value: object, name: str, maximum: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return normalized


def chain(value: object) -> str:
    return text(value, "chain", 64).lower()


def token(value: object) -> str:
    normalized = text(value, "token_address", 128)
    if normalized.lower().startswith("0x"):
        if not _EVM_ADDRESS.fullmatch(normalized.lower()):
            raise ValueError("token_address must be a 20-byte EVM address")
        return normalized.lower()
    return normalized


def block_hash(value: object) -> str:
    normalized = text(value, "block_hash", 66)
    if not _BLOCK_HASH.fullmatch(normalized):
        raise ValueError("block_hash must be a 32-byte hex value")
    return normalized.lower()


def block_number(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("block_number must be a non-negative integer")
    return value


def decimal_value(value: object, name: str, *, positive: bool = False) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a finite decimal") from exc
    if not result.is_finite():
        raise ValueError(f"{name} must be a finite decimal")
    if positive and result <= 0:
        raise ValueError(f"{name} must be positive")
    if not positive and result < 0:
        raise ValueError(f"{name} must be non-negative")
    return result


def decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    return "0" if normalized == 0 else format(normalized, "f")


def to_us(value: datetime, name: str) -> int:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError(f"{name} must be timezone-aware")
    utc = value.astimezone(UTC)
    delta = utc - _EPOCH
    return ((delta.days * 86_400 + delta.seconds) * 1_000_000) + delta.microseconds


def from_us(value: int) -> datetime:
    return _EPOCH + timedelta(microseconds=value)


def canonical_json(value: Mapping[str, object] | None) -> str:
    try:
        return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ValueError("metadata must be JSON serializable") from exc
