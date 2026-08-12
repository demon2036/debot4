"""Deterministic persistence values for reproducible research artifacts."""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
import json
from pathlib import Path
from typing import Iterable, Mapping

from .models import EvidenceReceipt, Observation


UTC = timezone.utc


def json_value(value: object) -> object:
    if is_dataclass(value):
        return json_value(asdict(value))
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    return value


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, values: Iterable[object]) -> None:
    lines = (
        json.dumps(json_value(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for value in values
    )
    path.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")


def observation_from_mapping(row: Mapping[str, object]) -> Observation:
    """Restore a validated observation from a persisted JSON-compatible row."""

    receipts = tuple(
        EvidenceReceipt(
            kind=str(item["kind"]),
            url=str(item["url"]),
            fetched_at=int(item["fetched_at"]),
            sha256=str(item["sha256"]),
            request_sha256=_text(item.get("request_sha256")),
            request_context=_text(item.get("request_context")),
        )
        for item in _mappings(row.get("receipts"))
    )
    return Observation(
        chain=str(row["chain"]), address=str(row["address"]),
        name=str(row["name"]), symbol=str(row["symbol"]),
        launchpad=str(row["launchpad"]), created_at=int(row["created_at"]),
        window_start=int(row["window_start"]),
        window_end_exclusive=int(row["window_end_exclusive"]),
        first_trade_at=_integer(row.get("first_trade_at")),
        first_price_usd=_decimal(row.get("first_price_usd")),
        peak_at=_integer(row.get("peak_at")),
        peak_price_usd=_decimal(row.get("peak_price_usd")),
        total_supply=_decimal(row.get("total_supply")),
        supply_source=_text(row.get("supply_source")),
        initial_fdv_usd=_decimal(row.get("initial_fdv_usd")),
        approx_peak_fdv_usd=_decimal(row.get("approx_peak_fdv_usd")),
        peak_multiple=_decimal(row.get("peak_multiple")),
        tiers=tuple(str(item) for item in row.get("tiers", ())),
        meets_peak_threshold=row.get("meets_peak_threshold") is True,
        current_kols=int(row["current_kols"]), max_kols=int(row["max_kols"]),
        precision=str(row["precision"]), status=str(row["status"]), receipts=receipts,
    )


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("persisted receipts must be a list of objects")
    return tuple(value)


def _decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _integer(value: object) -> int | None:
    return None if value is None else int(value)


def _text(value: object) -> str | None:
    return None if value is None else str(value)
