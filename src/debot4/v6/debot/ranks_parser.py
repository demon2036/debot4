"""Strict, bounded parsing for DeBot's BSC meme-ranks response."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from ..identity import bsc_address
from .ranks_models import RankSnapshot


STAGE_KEYS = {
    "new": "new_creations",
    "completing": "completing",
    "completed": "completed",
}


def parse_ranks(
    payload: Mapping[str, Any], stage: str, fetched_at: datetime,
) -> tuple[RankSnapshot, ...]:
    key = STAGE_KEYS.get(stage)
    if key is None:
        raise ValueError("unknown DeBot ranks stage")
    try:
        code = int(payload.get("code"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid DeBot ranks status") from exc
    data = payload.get("data")
    if code != 0 or not isinstance(data, Mapping):
        raise ValueError("unsuccessful DeBot ranks response")
    rows = data.get(key)
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("invalid DeBot ranks row set")
    output: dict[str, RankSnapshot] = {}
    for raw in rows:
        item = _snapshot(raw, stage, fetched_at)
        if item is not None:
            output[item.token_address] = item
    return tuple(output[address] for address in sorted(output))


def _snapshot(
    raw: object, stage: str, fetched_at: datetime,
) -> RankSnapshot | None:
    if not isinstance(raw, Mapping) or str(raw.get("chain") or "").lower() != "bsc":
        return None
    try:
        token = bsc_address(raw.get("contract"))
    except ValueError:
        return None
    stats = raw.get("meme_tag_stats")
    stats = stats if isinstance(stats, Mapping) else {}
    meta = raw.get("meta")
    meta = meta if isinstance(meta, Mapping) else {}
    kols = _integer(stats.get("kols"))
    if kols is None:
        kols = 0
    progress = _decimal(stats.get("progress")) or Decimal(0)
    migrated = _integer(stats.get("migratedTime")) or 0
    status = _integer(raw.get("status")) or 0
    return RankSnapshot(
        token_address=token,
        stage=stage,
        fetched_at=fetched_at,
        name=_text(meta.get("name") or raw.get("name"), 160),
        symbol=_text(meta.get("symbol") or raw.get("symbol"), 80),
        kols=kols,
        kol_aliases=_aliases(raw, stats),
        kol_holds=_decimal(stats.get("kolsHolds")),
        provider_fdv_usd=_market_cap(raw, stats),
        launched=(stage == "completed" or migrated > 0 or progress >= 1 or status >= 1),
    )


def _aliases(row: Mapping[str, Any], stats: Mapping[str, Any]) -> tuple[str, ...]:
    found: set[str] = set()
    for container in (row, stats):
        for key in ("kol_set", "kolSet", "kol_list", "kolList"):
            values = container.get(key)
            if not isinstance(values, list):
                continue
            for raw in values[:64]:
                if isinstance(raw, Mapping):
                    raw = raw.get("alias") or raw.get("name") or raw.get("address")
                value = str(raw or "").strip()
                if value:
                    found.add(value[:128])
    return tuple(sorted(found))


def _market_cap(row: Mapping[str, Any], stats: Mapping[str, Any]) -> Decimal | None:
    for raw in (row.get("market_cap"), row.get("marketCap"), stats.get("marketCap")):
        value = _decimal(raw)
        if value is not None:
            return value
    price = _decimal(stats.get("lastPrice"))
    supply = _decimal(stats.get("totalSupply"))
    return None if price is None or supply is None else price * supply


def _decimal(value: object) -> Decimal | None:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return result if result.is_finite() and result >= 0 else None


def _integer(value: object) -> int | None:
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result >= 0 else None


def _text(value: object, limit: int) -> str | None:
    result = str(value or "").strip()
    return result[:limit] if result else None
