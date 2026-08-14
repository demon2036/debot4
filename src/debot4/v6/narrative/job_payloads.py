"""Canonical JSON payloads for durable narrative research jobs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from hashlib import sha256
import json
from typing import Any, Mapping, TypeAlias

from ..domain import DeBotSignal, WalletTrade
from ..identity import canonical_json, utc_datetime
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .catalyst_mint import CatalystMintMatch
from .catalyst_mint_payload import (
    catalyst_mint_content,
    catalyst_mint_from_payload,
    catalyst_mint_payload,
)
from .market_job_payload import market_from_payload, market_payload
from .market_signal import MarketAnomaly


ACTIVE_X_POST = "active_x_post"
ACTIVE_TELEGRAM_POST = "active_telegram_post"
PASSIVE_DEBOT_SIGNAL = "passive_debot_signal"
PASSIVE_MARKET_ANOMALY = "passive_market_anomaly"
PASSIVE_CATALYST_MINT = "passive_catalyst_mint"
JOB_PAYLOAD_SCHEMA = "debot4.narrative-job-input.v1"
JOB_IDENTITY_SCHEMA = "debot4.narrative-job-identity.v1"
NarrativeJobInput: TypeAlias = (
    XPost | TelegramPost | DeBotSignal | MarketAnomaly | CatalystMintMatch
)


def encode_job_input(value: NarrativeJobInput) -> tuple[str, str, str, str]:
    """Return stable ID, kind, immutable-content hash, and full document."""

    if isinstance(value, XPost):
        kind = ACTIVE_X_POST
        payload = _x_post_payload(value)
        source_id = value.tweet_id
        content = {key: item for key, item in payload.items() if key != "fetched_at"}
    elif isinstance(value, TelegramPost):
        kind = ACTIVE_TELEGRAM_POST
        payload = _telegram_post_payload(value)
        source_id = value.source_id
        content = {key: item for key, item in payload.items() if key != "fetched_at"}
    elif isinstance(value, DeBotSignal):
        kind = PASSIVE_DEBOT_SIGNAL
        payload = _debot_signal_payload(value)
        source_id = value.signal_id
        volatile = {
            "available_at",
            "provider_fdv_usd",
            "provider_liquidity_usd",
            "security_hint",
            "raw_context",
        }
        content = {key: item for key, item in payload.items() if key not in volatile}
    elif isinstance(value, MarketAnomaly):
        kind = PASSIVE_MARKET_ANOMALY
        payload = market_payload(value)
        source_id = value.anomaly_id
        content = {"anomaly_id": value.anomaly_id}
    elif isinstance(value, CatalystMintMatch):
        kind = PASSIVE_CATALYST_MINT
        payload = catalyst_mint_payload(value)
        source_id = value.match_id
        content = catalyst_mint_content(value)
    else:
        raise TypeError("unsupported narrative job input")
    document = canonical_json(
        {"schema": JOB_PAYLOAD_SCHEMA, "kind": kind, "payload": payload}
    )
    identity = canonical_json(
        {"schema": JOB_IDENTITY_SCHEMA, "kind": kind, "source_id": source_id}
    )
    content_document = canonical_json({"kind": kind, "content": content})
    job_digest = sha256(identity.encode("utf-8")).hexdigest()
    content_digest = sha256(content_document.encode("utf-8")).hexdigest()
    return f"narrative-job-{job_digest}", kind, content_digest, document


def decode_job_input(document: str) -> tuple[str, NarrativeJobInput]:
    raw = json.loads(document)
    if not isinstance(raw, dict) or raw.get("schema") != JOB_PAYLOAD_SCHEMA:
        raise ValueError("invalid narrative job payload schema")
    kind = raw.get("kind")
    payload = raw.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("invalid narrative job payload")
    if kind == ACTIVE_X_POST:
        return kind, _x_post(payload)
    if kind == ACTIVE_TELEGRAM_POST:
        return kind, _telegram_post(payload)
    if kind == PASSIVE_DEBOT_SIGNAL:
        return kind, _debot_signal(payload)
    if kind == PASSIVE_MARKET_ANOMALY:
        return kind, market_from_payload(payload)
    if kind == PASSIVE_CATALYST_MINT:
        return kind, catalyst_mint_from_payload(payload)
    raise ValueError("invalid narrative job kind")


def _x_post_payload(post: XPost) -> dict[str, object]:
    return {
        "tweet_id": post.tweet_id,
        "author": post.author,
        "text": post.text,
        "created_at": utc_datetime(post.created_at).isoformat(),
        "fetched_at": utc_datetime(post.fetched_at).isoformat(),
        "post_type": post.post_type,
        "target_author": post.target_author,
        "target_text": post.target_text,
        "urls": list(post.urls),
        "bsc_contracts": list(post.bsc_contracts),
    }


def _x_post(payload: Mapping[str, Any]) -> XPost:
    return XPost(
        tweet_id=str(payload["tweet_id"]),
        author=str(payload["author"]),
        text=str(payload["text"]),
        created_at=_datetime(payload["created_at"]),
        fetched_at=_datetime(payload["fetched_at"]),
        post_type=str(payload.get("post_type", "post")),
        target_author=str(payload.get("target_author", "")),
        target_text=str(payload.get("target_text", "")),
        urls=tuple(str(item) for item in payload.get("urls", ())),
        bsc_contracts=tuple(str(item) for item in payload.get("bsc_contracts", ())),
    )


def _telegram_post_payload(post: TelegramPost) -> dict[str, object]:
    return {
        "channel": post.channel,
        "message_id": post.message_id,
        "text": post.text,
        "created_at": utc_datetime(post.created_at).isoformat(),
        "fetched_at": utc_datetime(post.fetched_at).isoformat(),
        "urls": list(post.urls),
        "bsc_contracts": list(post.bsc_contracts),
        "has_media": post.has_media,
    }


def _telegram_post(payload: Mapping[str, Any]) -> TelegramPost:
    return TelegramPost(
        channel=str(payload["channel"]),
        message_id=int(payload["message_id"]),
        text=str(payload["text"]),
        created_at=_datetime(payload["created_at"]),
        fetched_at=_datetime(payload["fetched_at"]),
        urls=tuple(str(item) for item in payload.get("urls", ())),
        bsc_contracts=tuple(str(item) for item in payload.get("bsc_contracts", ())),
        has_media=bool(payload.get("has_media")),
    )


def _wallet_payload(item: WalletTrade) -> dict[str, object]:
    return {
        "alias": item.alias,
        "wallet": item.wallet,
        "traded_at": utc_datetime(item.traded_at).isoformat(),
        "volume_usd": format(item.volume_usd, "f"),
        "token_amount": format(item.token_amount, "f"),
    }


def _debot_signal_payload(signal: DeBotSignal) -> dict[str, object]:
    return {
        "signal_id": signal.signal_id,
        "token_address": signal.token_address,
        "signal_kind": signal.signal_kind,
        "group_name": signal.group_name,
        "event_at": utc_datetime(signal.event_at).isoformat(),
        "available_at": utc_datetime(signal.available_at).isoformat(),
        "channel_id": signal.channel_id,
        "pair_address": signal.pair_address,
        "dex_name": signal.dex_name,
        "token_name": signal.token_name,
        "token_symbol": signal.token_symbol,
        "token_decimals": signal.token_decimals,
        "total_supply": _decimal_text(signal.total_supply),
        "created_at": _datetime_text(signal.created_at),
        "provider_fdv_usd": _decimal_text(signal.provider_fdv_usd),
        "provider_liquidity_usd": _decimal_text(signal.provider_liquidity_usd),
        "narrative_urls": list(signal.narrative_urls),
        "description": signal.description,
        "wallet_trades": [_wallet_payload(item) for item in signal.wallet_trades],
        "kol_buy_qualified": signal.kol_buy_qualified,
        "kol_buy_reason": signal.kol_buy_reason,
        "security_hint": signal.security_hint,
        "raw_context": signal.raw_context,
    }


def _debot_signal(payload: Mapping[str, Any]) -> DeBotSignal:
    raw_wallets = payload.get("wallet_trades", ())
    if not isinstance(raw_wallets, list):
        raise ValueError("invalid DeBot wallet evidence")
    return DeBotSignal(
        signal_id=str(payload["signal_id"]),
        token_address=str(payload["token_address"]),
        signal_kind=str(payload["signal_kind"]),
        group_name=str(payload["group_name"]),
        event_at=_datetime(payload["event_at"]),
        available_at=_datetime(payload["available_at"]),
        channel_id=str(payload["channel_id"]),
        pair_address=_optional_text(payload.get("pair_address")),
        dex_name=_optional_text(payload.get("dex_name")),
        token_name=_optional_text(payload.get("token_name")),
        token_symbol=_optional_text(payload.get("token_symbol")),
        token_decimals=_optional_int(payload.get("token_decimals")),
        total_supply=_optional_decimal(payload.get("total_supply")),
        created_at=_optional_datetime(payload.get("created_at")),
        provider_fdv_usd=_optional_decimal(payload.get("provider_fdv_usd")),
        provider_liquidity_usd=_optional_decimal(
            payload.get("provider_liquidity_usd")
        ),
        narrative_urls=tuple(str(item) for item in payload.get("narrative_urls", ())),
        description=_optional_text(payload.get("description")),
        wallet_trades=tuple(_wallet(item) for item in raw_wallets),
        kol_buy_qualified=bool(payload.get("kol_buy_qualified")),
        kol_buy_reason=str(payload.get("kol_buy_reason", "")),
        security_hint=_mapping(payload.get("security_hint")),
        raw_context=_mapping(payload.get("raw_context")),
    )


def _wallet(payload: object) -> WalletTrade:
    if not isinstance(payload, dict):
        raise ValueError("invalid DeBot wallet evidence")
    return WalletTrade(
        alias=str(payload["alias"]),
        wallet=_optional_text(payload.get("wallet")),
        traded_at=_datetime(payload["traded_at"]),
        volume_usd=Decimal(str(payload["volume_usd"])),
        token_amount=Decimal(str(payload["token_amount"])),
    )


def _datetime(value: object) -> datetime:
    return utc_datetime(datetime.fromisoformat(str(value)))


def _optional_datetime(value: object) -> datetime | None:
    return None if value is None else _datetime(value)


def _datetime_text(value: datetime | None) -> str | None:
    return None if value is None else utc_datetime(value).isoformat()


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


def _decimal_text(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _optional_int(value: object) -> int | None:
    return None if value is None else int(value)


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}
