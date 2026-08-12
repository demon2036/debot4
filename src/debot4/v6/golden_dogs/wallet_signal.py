"""Pure wallet-selectivity rules; profit and public identity are not eligibility gates."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WalletSignalVerdict(str, Enum):
    CANDIDATE = "CANDIDATE"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class WalletSignalHistory:
    wallet: str
    x_handle: str | None
    period_start: int
    period_end_exclusive: int
    unique_tokens_bought: int
    buy_transactions: int
    pre_peak_gold_hits: int
    outcomes_complete: bool
    activity_coverage_complete: bool

    def __post_init__(self) -> None:
        if not 0 < self.period_start < self.period_end_exclusive:
            raise ValueError("wallet signal period is invalid")
        values = (
            self.unique_tokens_bought, self.buy_transactions, self.pre_peak_gold_hits,
        )
        if min(values) < 0 or self.pre_peak_gold_hits > self.unique_tokens_bought:
            raise ValueError("wallet signal counts are invalid")


@dataclass(frozen=True, slots=True)
class WalletSignalAssessment:
    verdict: WalletSignalVerdict
    hit_rate: float | None
    reasons: tuple[str, ...]


def assess_wallet_signal(
    history: WalletSignalHistory,
    *,
    minimum_tokens: int = 10,
    maximum_tokens_per_day: float = 8.0,
    minimum_hit_rate: float = 0.20,
) -> WalletSignalAssessment:
    """Reward selective early hits and reject indiscriminate high-frequency buyers."""

    if not history.activity_coverage_complete or not history.outcomes_complete:
        return WalletSignalAssessment(WalletSignalVerdict.WAIT, None, ("history_incomplete",))
    days = max(1.0, (history.period_end_exclusive - history.period_start) / 86_400)
    tokens_per_day = history.unique_tokens_bought / days
    if tokens_per_day > maximum_tokens_per_day:
        return WalletSignalAssessment(
            WalletSignalVerdict.REJECT, None, ("indiscriminate_high_frequency_buyer",),
        )
    if history.unique_tokens_bought < minimum_tokens:
        return WalletSignalAssessment(WalletSignalVerdict.WAIT, None, ("denominator_too_small",))
    rate = history.pre_peak_gold_hits / history.unique_tokens_bought
    if rate < minimum_hit_rate:
        return WalletSignalAssessment(WalletSignalVerdict.REJECT, rate, ("early_hit_rate_too_low",))
    identity = "x_attributed" if history.x_handle else "anonymous_wallet"
    return WalletSignalAssessment(
        WalletSignalVerdict.CANDIDATE, rate, (f"selective_early_hits:{identity}",),
    )
