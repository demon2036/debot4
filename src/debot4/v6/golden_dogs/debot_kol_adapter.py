"""Adapt qualified DeBot provider signals into golden-dog KOL-buy evidence."""

from __future__ import annotations

from ..domain import DeBotSignal
from .qualification import KolWalletTrade, ProviderKolBuy


def provider_buy_from_debot(signal: DeBotSignal) -> ProviderKolBuy:
    if signal.signal_kind != "kol" or not signal.kol_buy_qualified:
        raise ValueError("DeBot signal is not qualified provider KOL-buy evidence")
    trades = tuple(
        KolWalletTrade(
            provider_alias=item.alias,
            wallet=item.wallet,
            bought_at=int(item.traded_at.timestamp()),
            volume_usd=item.volume_usd,
            token_amount=item.token_amount,
        )
        for item in signal.wallet_trades
    )
    return ProviderKolBuy(
        provider="debot",
        chain="bsc",
        token_address=signal.token_address,
        signal_id=signal.signal_id,
        provider_event_at=int(signal.event_at.timestamp()),
        provider_url=signal.evidence_uri,
        trades=trades,
    )
