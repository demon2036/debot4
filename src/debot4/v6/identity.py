"""Canonical identifiers and JSON-safe metadata helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import re
from typing import Any, Mapping


UTC = timezone.utc
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


def bsc_address(value: object) -> str:
    text = str(value or "").strip()
    if not _ADDRESS.fullmatch(text):
        raise ValueError("invalid BSC address")
    return text.lower()


def stable_id(prefix: str, *parts: object) -> str:
    body = "\x1f".join(str(part) for part in parts)
    return f"{prefix}-{sha256(body.encode('utf-8')).hexdigest()[:32]}"


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else None
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return utc_datetime(value).isoformat()
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item) for item in value]
    return str(value)


def canonical_json(value: Mapping[str, Any]) -> str:
    return json.dumps(
        json_safe(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
