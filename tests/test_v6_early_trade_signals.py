from __future__ import annotations

from decimal import Decimal

from debot4.v6.golden_dogs.early_trade_signals import (
    EarlyTradeSignalClass,
    classify_early_trade,
)
from debot4.v6.golden_dogs.gmgn_market_trades import GmgnMarketTrade


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
TX = "0x" + "c" * 64


def trade(*tags: str) -> GmgnMarketTrade:
    return GmgnMarketTrade(
        WALLET, CA, "buy", 100, Decimal("1"), Decimal("1"), Decimal("1"),
        TX, "", None, tuple(tags), (), (),
    )


def test_provider_smart_tag_is_candidate_not_qualified_wallet() -> None:
    result = classify_early_trade(trade("smart_degen"))
    assert result.classification == EarlyTradeSignalClass.PROVIDER_SMART_CANDIDATE
    assert result.reasons == ("provider_label_only_requires_wallet_history",)


def test_manipulation_tag_overrides_smart_tag() -> None:
    result = classify_early_trade(trade("smart_degen", "wash_trader"))
    assert result.classification == EarlyTradeSignalClass.MANIPULATIVE
    assert result.matched_tags == ("wash_trader",)


def test_kol_label_is_not_called_smart_money() -> None:
    result = classify_early_trade(trade("kol"))
    assert result.classification == EarlyTradeSignalClass.KOL_TAGGED
