"""Translate provider rank rows into provider-independent token seeds."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .debot_public import PublicDeBotError
from .models import TokenSeed


def parse_seed(row: Mapping[str, Any], source: str) -> TokenSeed:
    meta = _object(row.get("meta"), "rank metadata")
    stats = _object(row.get("meme_tag_stats"), "rank statistics")
    decimals = _integer(meta.get("decimals"))
    raw_supply = _decimal(meta.get("total_supply"))
    supply = None
    if raw_supply is not None and decimals is not None:
        supply = raw_supply / (Decimal(10) ** decimals)
    creator = str(meta.get("dev_address") or "").strip().casefold() or None
    return TokenSeed(
        chain=str(row.get("chain") or ""),
        address=str(row.get("contract") or ""),
        name=str(meta.get("name") or ""),
        symbol=str(meta.get("symbol") or ""),
        launchpad=str(meta.get("launchpad") or source),
        created_at=_integer(meta.get("create_time")) or 0,
        creator_address=creator,
        rank_supply=supply,
        current_kols=_integer(stats.get("kols")) or 0,
        max_kols=_integer(stats.get("kolsMax")) or 0,
        social_urls=_social_urls(row.get("social_info")),
        discovered_sources=(source,),
    )


def merge_seeds(existing: TokenSeed, incoming: TokenSeed) -> TokenSeed:
    if (existing.chain, existing.address) != (incoming.chain, incoming.address):
        raise ValueError("cannot merge different token seeds")
    return TokenSeed(
        chain=existing.chain,
        address=existing.address,
        name=existing.name or incoming.name,
        symbol=existing.symbol or incoming.symbol,
        launchpad=existing.launchpad or incoming.launchpad,
        created_at=min(existing.created_at, incoming.created_at),
        creator_address=existing.creator_address or incoming.creator_address,
        rank_supply=existing.rank_supply or incoming.rank_supply,
        current_kols=max(existing.current_kols, incoming.current_kols),
        max_kols=max(existing.max_kols, incoming.max_kols),
        social_urls=existing.social_urls + incoming.social_urls,
        discovered_sources=existing.discovered_sources + incoming.discovered_sources,
    )


def _object(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise PublicDeBotError(f"DeBot {label} is not an object")
    return value


def _decimal(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool) or str(value).strip() == "":
        return None
    try:
        number = Decimal(str(value))
    except InvalidOperation as exc:
        raise PublicDeBotError("DeBot rank contains an invalid number") from exc
    return number if number.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None


def _social_urls(value: object) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ()
    urls: list[str] = []
    for item in value.values():
        if isinstance(item, str) and item.startswith(("http://", "https://")):
            urls.append(item)
        elif isinstance(item, list):
            urls.extend(
                entry for entry in item
                if isinstance(entry, str) and entry.startswith(("http://", "https://"))
            )
    return tuple(dict.fromkeys(urls))
