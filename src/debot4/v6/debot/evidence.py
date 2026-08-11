"""Auditable ledger metadata derived from parsed DeBot records."""

from __future__ import annotations

from .parser import _KOL_GROUP
from ..domain import DeBotSignal
from ..identity import json_safe, stable_id


SOURCE = "debot:bsc:official-signal"


def candidate_metadata(signal: DeBotSignal) -> dict[str, object]:
    return json_safe({
        "schema": "debot_candidate.v1",
        "name": signal.token_name,
        "symbol": signal.token_symbol,
        "pair_address": signal.pair_address,
        "dex_name": signal.dex_name,
        "created_at": signal.created_at,
        "provider_fdv_usd": signal.provider_fdv_usd,
        "provider_liquidity_usd": signal.provider_liquidity_usd,
        "narrative_urls": signal.narrative_urls,
        "description": signal.description,
    })


def signal_metadata(signal: DeBotSignal) -> dict[str, object]:
    return json_safe({
        "schema": "debot_current_signal.v1",
        "group_name": signal.group_name,
        "channel_id": signal.channel_id,
        "pair_address": signal.pair_address,
        "dex_name": signal.dex_name,
        "name": signal.token_name,
        "symbol": signal.token_symbol,
        "provider_fdv_usd": signal.provider_fdv_usd,
        "provider_liquidity_usd": signal.provider_liquidity_usd,
        "narrative_urls": signal.narrative_urls,
        "description": signal.description,
        "wallet_trades": [_wallet(item) for item in signal.wallet_trades],
        "kol_buy_qualified": signal.kol_buy_qualified,
        "kol_buy_reason": signal.kol_buy_reason,
        "raw_context": signal.raw_context,
    })


def kol_evidence_metadata(signal: DeBotSignal) -> dict[str, object]:
    match = _KOL_GROUP.match(signal.group_name)
    minutes = int(match.group("minutes")) if match else None
    return json_safe({
        "schema": "debot.v6.kol_buy_evidence.v1",
        "signal_group": "KOL",
        "provider_kol_buy_evidence": {
            "evidence_contract_version": 1,
            "qualified": signal.kol_buy_qualified,
            "is_kol_buy": signal.kol_buy_qualified,
            "status": "provider_ui_asserted",
            "reason": signal.kol_buy_reason,
            "verification_level": "provider_ui_asserted",
            "chain_verified": False,
            "provider_channel_id": signal.channel_id,
            "provider_group_name": signal.group_name,
            "provider_group_window_minutes": minutes,
            "provider_event_time_ms": int(signal.event_at.timestamp() * 1000),
            "buy_semantics_source": "debot.v6.parser.windowed_kol_wallet_trades",
            "kol_wallet_count": len(signal.wallet_trades),
            "kol_wallet_identifiers": [_provider_wallet(item) for item in signal.wallet_trades],
        },
    })


def evidence_id(signal: DeBotSignal) -> str:
    return stable_id("kol", signal.signal_id, signal.token_address)


def _wallet(item: object) -> dict[str, object]:
    return json_safe({
        "alias": getattr(item, "alias"),
        "wallet": getattr(item, "wallet"),
        "traded_at": getattr(item, "traded_at"),
        "volume_usd": getattr(item, "volume_usd"),
        "token_amount": getattr(item, "token_amount"),
    })


def _provider_wallet(item: object) -> dict[str, object]:
    return json_safe({
        "provider_wallet_alias": getattr(item, "alias"),
        "provider_wallet_address": getattr(item, "wallet"),
        "provider_trade_time_ms": int(getattr(item, "traded_at").timestamp() * 1000),
        "provider_volume_usd": getattr(item, "volume_usd"),
    })
