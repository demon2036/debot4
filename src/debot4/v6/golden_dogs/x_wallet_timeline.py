"""Pure timing labels for optional wallet evidence attached to an X post."""

from __future__ import annotations

from enum import Enum


class WalletPostTiming(str, Enum):
    BUY_BEFORE_POST = "buy_before_post"
    BUY_AFTER_POST_BEFORE_PEAK = "buy_after_post_before_peak"
    BUY_AFTER_PEAK = "buy_after_peak"


def classify_wallet_post_timing(
    *, buy_at: int, post_at: int, peak_at: int,
) -> WalletPostTiming:
    """Classify exact-wallet/exact-CA evidence without imposing a lead-time cap."""

    if min(buy_at, post_at, peak_at) <= 0:
        raise ValueError("wallet/post/peak timestamps must be positive")
    if post_at >= peak_at:
        raise ValueError("wallet timeline requires a pre-peak X post")
    if buy_at < post_at:
        return WalletPostTiming.BUY_BEFORE_POST
    if buy_at < peak_at:
        return WalletPostTiming.BUY_AFTER_POST_BEFORE_PEAK
    return WalletPostTiming.BUY_AFTER_PEAK
