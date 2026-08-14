"""JSON value codec for catalyst-mint observations."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from ..debot.ranks_models import RankSnapshot
from ..identity import utc_datetime
from ..x.models import XPost


def encode_post(value: XPost) -> dict[str, object]:
    return {
        "tweet_id": value.tweet_id, "author": value.author, "text": value.text,
        "created_at": value.created_at.isoformat(), "fetched_at": value.fetched_at.isoformat(),
        "post_type": value.post_type, "target_author": value.target_author,
        "target_text": value.target_text, "urls": list(value.urls),
        "bsc_contracts": list(value.bsc_contracts),
    }


def decode_post(value: object) -> XPost:
    if not isinstance(value, dict):
        raise ValueError("post state must be an object")
    return XPost(
        str(value["tweet_id"]), str(value["author"]), str(value["text"]),
        _time(value["created_at"]), _time(value["fetched_at"]),
        str(value.get("post_type", "post")), str(value.get("target_author", "")),
        str(value.get("target_text", "")), tuple(map(str, value.get("urls", ()))),
        tuple(map(str, value.get("bsc_contracts", ()))),
    )


def encode_mint(value: RankSnapshot) -> dict[str, object]:
    return {
        "token_address": value.token_address, "stage": value.stage,
        "fetched_at": value.fetched_at.isoformat(), "name": value.name,
        "symbol": value.symbol, "kols": value.kols,
        "kol_aliases": list(value.kol_aliases), "kol_holds": _decimal(value.kol_holds),
        "provider_fdv_usd": _decimal(value.provider_fdv_usd),
        "launched": value.launched,
        "created_at": value.created_at.isoformat() if value.created_at else None,
        "launchpad": value.launchpad, "description": value.description,
        "social_urls": list(value.social_urls),
    }


def decode_mint(value: object) -> RankSnapshot:
    if not isinstance(value, dict):
        raise ValueError("mint state must be an object")
    return RankSnapshot(
        str(value["token_address"]), str(value["stage"]), _time(value["fetched_at"]),
        _optional(value.get("name")), _optional(value.get("symbol")), int(value["kols"]),
        tuple(map(str, value.get("kol_aliases", ()))),
        _optional_decimal(value.get("kol_holds")),
        _optional_decimal(value.get("provider_fdv_usd")), bool(value["launched"]),
        _optional_time(value.get("created_at")), _optional(value.get("launchpad")),
        _optional(value.get("description")), tuple(map(str, value.get("social_urls", ()))),
    )


def _time(value: object) -> datetime:
    return utc_datetime(datetime.fromisoformat(str(value)))


def _optional_time(value: object) -> datetime | None:
    return None if value is None else _time(value)


def _optional(value: object) -> str | None:
    return None if value is None else str(value)


def _decimal(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))
