"""Translate one exact-CA DeBot response into a provider-independent seed."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .debot_public import PublicDeBotError, TokenDetailPage
from .models import TokenSeed


def parse_detail_seed(page: TokenDetailPage, source: str = "exact_ca_audit") -> TokenSeed:
    meta = _object(page.data.get("meta"), "token metadata")
    decimals = _integer(meta.get("decimals"))
    raw_supply = _decimal(meta.get("total_supply"))
    supply = None
    if raw_supply is not None and decimals is not None:
        supply = raw_supply / (Decimal(10) ** decimals)
    creator = str(meta.get("creator_address") or "").strip().casefold() or None
    return TokenSeed(
        chain=str(meta.get("chain") or ""),
        address=str(meta.get("address") or ""),
        name=str(meta.get("name") or ""),
        symbol=str(meta.get("symbol") or ""),
        launchpad=str(meta.get("launchpad") or source),
        created_at=_integer(meta.get("creation_timestamp")) or 0,
        creator_address=creator,
        rank_supply=supply,
        current_kols=0,
        max_kols=0,
        social_urls=_social_urls(page.data.get("social")),
        discovered_sources=(source,),
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
        raise PublicDeBotError("DeBot token detail contains an invalid number") from exc
    return number if number.is_finite() else None


def _integer(value: object) -> int | None:
    number = _decimal(value)
    return int(number) if number is not None and number == number.to_integral() else None


def _social_urls(value: object) -> tuple[str, ...]:
    if not isinstance(value, dict):
        return ()
    return tuple(
        dict.fromkeys(
            item for item in value.values()
            if isinstance(item, str) and item.startswith(("http://", "https://"))
        )
    )
