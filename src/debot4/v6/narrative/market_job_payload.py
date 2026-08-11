"""Canonical serializer for durable BSC market-anomaly jobs."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Mapping

from ..identity import utc_datetime
from .market_signal import MarketAnomaly


def market_payload(value: MarketAnomaly) -> dict[str, object]:
    return {
        "anomaly_id": value.anomaly_id,
        "exact_ca": value.exact_ca,
        "observed_at": value.observed_at.isoformat(),
        "symbol": value.symbol,
        "name": value.name,
        "h1_change_pct": format(value.h1_change_pct, "f"),
        "liquidity_usd": format(value.liquidity_usd, "f"),
        "valuation_usd": format(value.valuation_usd, "f"),
        "volume_h1_usd": format(value.volume_h1_usd, "f"),
        "txns_h1": value.txns_h1,
        "stage_pct": format(value.stage_pct, "f"),
        "source": value.source,
        "source_url": value.source_url,
    }


def market_from_payload(payload: Mapping[str, Any]) -> MarketAnomaly:
    value = MarketAnomaly(
        exact_ca=str(payload["exact_ca"]),
        observed_at=utc_datetime(datetime.fromisoformat(str(payload["observed_at"]))),
        symbol=str(payload.get("symbol", "")),
        name=str(payload.get("name", "")),
        h1_change_pct=Decimal(str(payload["h1_change_pct"])),
        liquidity_usd=Decimal(str(payload["liquidity_usd"])),
        valuation_usd=Decimal(str(payload["valuation_usd"])),
        volume_h1_usd=Decimal(str(payload["volume_h1_usd"])),
        txns_h1=int(payload["txns_h1"]),
        stage_pct=Decimal(str(payload["stage_pct"])),
        source=str(payload["source"]),
        source_url=str(payload["source_url"]),
    )
    if payload.get("anomaly_id") != value.anomaly_id:
        raise ValueError("market anomaly identity mismatch")
    return value
