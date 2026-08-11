"""Adapter from a market anomaly to the shared passive narrative gate."""

from __future__ import annotations

from .market_signal import MarketAnomaly
from .passive_trigger import PassiveNarrativeTrigger


def passive_trigger_from_market(anomaly: MarketAnomaly) -> PassiveNarrativeTrigger:
    return PassiveNarrativeTrigger(
        exact_ca=anomaly.exact_ca,
        signal_id=anomaly.anomaly_id,
        observed_at=anomaly.observed_at,
        token_name=anomaly.name or None,
        token_symbol=anomaly.symbol or None,
        anomaly=anomaly.describe(),
    )
