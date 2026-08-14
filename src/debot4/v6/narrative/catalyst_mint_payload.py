"""Canonical job payload codec for deterministic catalyst-mint matches."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from ..identity import utc_datetime
from .catalyst_mint import CatalystMintMatch, MATCH_KIND


def catalyst_mint_payload(value: CatalystMintMatch) -> dict[str, object]:
    return {
        "match_id": value.match_id,
        "match_kind": value.match_kind,
        "exact_ca": value.exact_ca,
        "token_stage": value.token_stage,
        "token_created_at": value.token_created_at.isoformat(),
        "observed_at": value.observed_at.isoformat(),
        "token_name": value.token_name,
        "token_symbol": value.token_symbol,
        "provider_fdv_usd": _decimal(value.provider_fdv_usd),
        "launchpad": value.launchpad,
        "token_description": value.token_description,
        "token_social_urls": list(value.token_social_urls),
        "token_status_url": value.token_status_url,
        "catalyst_tweet_id": value.catalyst_tweet_id,
        "catalyst_author": value.catalyst_author,
        "catalyst_text": value.catalyst_text,
        "catalyst_created_at": value.catalyst_created_at.isoformat(),
        "catalyst_fetched_at": value.catalyst_fetched_at.isoformat(),
        "authorizes_trade": False,
    }


def catalyst_mint_from_payload(payload: Mapping[str, Any]) -> CatalystMintMatch:
    if payload.get("match_kind") != MATCH_KIND or payload.get("authorizes_trade") is not False:
        raise ValueError("invalid catalyst mint binding semantics")
    value = CatalystMintMatch(
        exact_ca=str(payload["exact_ca"]),
        token_stage=str(payload.get("token_stage", "new")),
        token_created_at=_time(payload["token_created_at"]),
        observed_at=_time(payload["observed_at"]),
        token_name=_optional(payload.get("token_name")),
        token_symbol=_optional(payload.get("token_symbol")),
        provider_fdv_usd=_optional_decimal(payload.get("provider_fdv_usd")),
        launchpad=_optional(payload.get("launchpad")),
        token_description=_optional(payload.get("token_description")),
        token_social_urls=tuple(map(str, payload.get("token_social_urls", ()))),
        token_status_url=str(payload["token_status_url"]),
        catalyst_tweet_id=str(payload["catalyst_tweet_id"]),
        catalyst_author=str(payload["catalyst_author"]),
        catalyst_text=str(payload["catalyst_text"]),
        catalyst_created_at=_time(payload["catalyst_created_at"]),
        catalyst_fetched_at=_time(payload["catalyst_fetched_at"]),
    )
    if payload.get("match_id") != value.match_id:
        raise ValueError("catalyst mint match ID is inconsistent")
    return value


def catalyst_mint_content(value: CatalystMintMatch) -> dict[str, object]:
    """Immutable binding identity; provider enrichment may refresh pending payloads."""

    return {
        "match_id": value.match_id,
        "exact_ca": value.exact_ca,
        "token_created_at": value.token_created_at.isoformat(),
        "catalyst_tweet_id": value.catalyst_tweet_id,
        "catalyst_created_at": value.catalyst_created_at.isoformat(),
    }


def _time(value: object) -> datetime:
    return utc_datetime(datetime.fromisoformat(str(value)))


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))
