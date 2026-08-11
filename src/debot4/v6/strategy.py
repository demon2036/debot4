"""Explicit hard gates for the non-narrative execution inputs."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from .config import StrategyConfig
from .domain import DeBotSignal, ExecutionQuote, GateResult, SecuritySnapshot


UTC = timezone.utc
BPS = Decimal(10_000)


def signal_gate(
    signal: DeBotSignal, rules: StrategyConfig, *, now: datetime | None = None
) -> GateResult:
    checked = now or datetime.now(UTC)
    age = (checked - signal.event_at).total_seconds()
    reasons = []
    if signal.signal_kind not in {"kol", "smart_money"}:
        reasons.append("unsupported_debot_signal")
    if signal.channel_id != "2":
        reasons.append("not_official_debot_channel")
    if signal.signal_kind == "kol" and not signal.kol_buy_qualified:
        reasons.append(f"kol_not_qualified:{signal.kol_buy_reason}")
    if age < -1:
        reasons.append("signal_from_future")
    elif age > rules.signal_max_age_seconds:
        reasons.append("signal_stale")
    if not signal.pair_address:
        reasons.append("pair_missing")
    return GateResult(
        not reasons,
        "signal_passed" if not reasons else reasons[0],
        {"all_reasons": reasons, "signal_age_seconds": age},
    )


def security_gate(snapshot: SecuritySnapshot, rules: StrategyConfig) -> GateResult:
    reasons = []
    required_false = {
        "honeypot": snapshot.is_honeypot,
        "cannot_buy": snapshot.cannot_buy,
        "cannot_sell_all": snapshot.cannot_sell_all,
        "proxy": snapshot.is_proxy,
        "hidden_owner": snapshot.hidden_owner,
        "owner_change_balance": snapshot.owner_change_balance,
    }
    reasons.extend(f"security_unknown:{name}" for name, value in required_false.items() if value is None)
    reasons.extend(f"security_reject:{name}" for name, value in required_false.items() if value is True)
    if rules.require_open_source and snapshot.is_open_source is not True:
        reasons.append("contract_not_verified_open_source")
    if snapshot.buy_tax_pct is None or snapshot.sell_tax_pct is None:
        reasons.append("tax_unknown")
    else:
        if snapshot.buy_tax_pct > rules.max_buy_tax_pct:
            reasons.append("buy_tax_too_high")
        if snapshot.sell_tax_pct > rules.max_sell_tax_pct:
            reasons.append("sell_tax_too_high")
    return GateResult(
        not reasons,
        "security_passed" if not reasons else reasons[0],
        {"all_reasons": reasons},
    )


def quote_gate(
    quote: ExecutionQuote, rules: StrategyConfig, *, now: datetime | None = None
) -> GateResult:
    checked = now or datetime.now(UTC)
    age = (checked - quote.state.head.timestamp).total_seconds()
    fetch_age = (checked - quote.state.head.fetched_at).total_seconds()
    round_trip_loss = max(
        Decimal(0), (quote.notional_usd - quote.immediate_exit_usd)
        / quote.notional_usd * BPS,
    )
    reasons = []
    if age < -1 or fetch_age < -1:
        reasons.append("quote_from_future")
    if age > rules.max_block_age_seconds:
        reasons.append("quote_block_stale")
    if fetch_age > rules.max_quote_age_seconds:
        reasons.append("quote_fetch_stale")
    if quote.spot_fdv_usd < rules.min_fdv_usd:
        reasons.append("fdv_below_minimum")
    if quote.fill_fdv_usd > rules.max_fdv_usd:
        reasons.append("fill_fdv_above_maximum")
    if quote.liquidity_usd < rules.min_liquidity_usd:
        reasons.append("liquidity_below_minimum")
    if quote.price_impact_bps > rules.max_price_impact_bps:
        reasons.append("price_impact_too_high")
    if round_trip_loss > rules.max_round_trip_loss_bps:
        reasons.append("round_trip_loss_too_high")
    return GateResult(
        not reasons,
        "quote_passed" if not reasons else reasons[0],
        {
            "all_reasons": reasons,
            "block_age_seconds": age,
            "quote_fetch_age_seconds": fetch_age,
            "round_trip_loss_bps": round_trip_loss,
        },
    )
