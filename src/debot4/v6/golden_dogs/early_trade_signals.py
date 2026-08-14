"""Pure conservative labels for early unfiltered token trades."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from .gmgn_market_trades import GmgnMarketTrade
from .wallet_risk import manipulative_wallet_tags


PROVIDER_SMART_TAGS = frozenset({
    "smart_degen",
    "app_smart_money",
    "launchpad_smart",
})


class EarlyTradeSignalClass(str, Enum):
    PROVIDER_SMART_CANDIDATE = "provider_smart_candidate"
    KOL_TAGGED = "kol_tagged"
    ORDINARY = "ordinary"
    MANIPULATIVE = "manipulative"


@dataclass(frozen=True, slots=True)
class EarlyTradeSignal:
    classification: EarlyTradeSignalClass
    matched_tags: tuple[str, ...]
    reasons: tuple[str, ...]


def classify_early_trade(trade: GmgnMarketTrade) -> EarlyTradeSignal:
    """Classify provider metadata without claiming wallet skill or causality."""

    if trade.event != "buy":
        raise ValueError("only buys can be early trade signals")
    risky = manipulative_wallet_tags(trade.wallet_tags)
    if risky:
        return EarlyTradeSignal(
            EarlyTradeSignalClass.MANIPULATIVE,
            risky,
            ("provider_manipulation_tag",),
        )
    smart = tuple(sorted(PROVIDER_SMART_TAGS & set(trade.wallet_tags)))
    if smart:
        return EarlyTradeSignal(
            EarlyTradeSignalClass.PROVIDER_SMART_CANDIDATE,
            smart,
            ("provider_label_only_requires_wallet_history",),
        )
    if "kol" in trade.wallet_tags:
        return EarlyTradeSignal(
            EarlyTradeSignalClass.KOL_TAGGED,
            ("kol",),
            ("provider_kol_label_only_requires_identity_and_history",),
        )
    return EarlyTradeSignal(
        EarlyTradeSignalClass.ORDINARY,
        (),
        ("no_supported_provider_signal_tag",),
    )


def is_provider_smart_candidate(tags: Iterable[str]) -> bool:
    normalized = {str(tag).strip().casefold() for tag in tags if str(tag).strip()}
    return bool(PROVIDER_SMART_TAGS & normalized) and not manipulative_wallet_tags(normalized)
