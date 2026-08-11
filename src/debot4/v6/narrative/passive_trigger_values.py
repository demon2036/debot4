"""Normalize and describe untrusted values entering passive narrative search."""

from __future__ import annotations

from urllib.parse import urlsplit

from ..domain import DeBotSignal
from ..identity import utc_datetime


def describe_signal_anomaly(signal: DeBotSignal) -> str:
    pieces = [f"DeBot {signal.signal_kind} signal in group {signal.group_name}"]
    pieces += [
        f"provider_event_at={utc_datetime(signal.event_at).isoformat()}",
        f"wallet_trade_count={len(signal.wallet_trades)}",
        f"kol_buy_qualified={str(signal.kol_buy_qualified).lower()}",
        f"kol_buy_reason={signal.kol_buy_reason}",
    ]
    if signal.provider_fdv_usd is not None:
        pieces.append(f"provider_fdv_usd={signal.provider_fdv_usd}")
    if signal.provider_liquidity_usd is not None:
        pieces.append(f"provider_liquidity_usd={signal.provider_liquidity_usd}")
    return "; ".join(pieces)


def bounded_social_urls(urls: tuple[str, ...]) -> tuple[str, ...]:
    accepted: list[str] = []
    for value in urls:
        url = str(value).strip()
        if not url or len(url) > 2_048 or any(char.isspace() for char in url):
            continue
        try:
            parsed = urlsplit(url)
            valid = (
                parsed.scheme.lower() in {"http", "https"}
                and bool(parsed.hostname)
                and not parsed.username
                and not parsed.password
            )
        except ValueError:
            valid = False
        if valid and url not in accepted:
            accepted.append(url)
    return tuple(accepted)


def optional_text(value: str | None, limit: int) -> str | None:
    text = str(value or "").strip()
    return text[:limit] or None
