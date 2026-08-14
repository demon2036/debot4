"""Pure descriptive statistics for reviewed X-first golden-dog signals."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median


@dataclass(frozen=True, slots=True)
class ReviewedSignal:
    address: str
    stable_user_id: str
    post_at: int
    seconds_to_peak: int
    post_to_peak_multiple: Decimal
    semantic: str
    account_role: str
    author_wallet_buys_before_post: int

    def __post_init__(self) -> None:
        if not self.address.startswith("0x") or len(self.address) != 42:
            raise ValueError("reviewed signal needs an exact EVM address")
        if self.post_at <= 0 or self.seconds_to_peak < 0:
            raise ValueError("reviewed signal timing is invalid")
        if self.post_to_peak_multiple <= 0 or self.author_wallet_buys_before_post < 0:
            raise ValueError("reviewed signal measurements are invalid")


def summarize_reviewed_signals(
    signals: tuple[ReviewedSignal, ...],
) -> dict[str, object]:
    """Describe reviewed rows without treating selected winners as a win-rate sample."""

    ordered = tuple(sorted(signals, key=lambda item: (
        item.address, item.post_at, item.stable_user_id,
    )))
    first_by_token: dict[str, ReviewedSignal] = {}
    for item in ordered:
        first_by_token.setdefault(item.address, item)
    first = tuple(first_by_token.values())
    return {
        "reviewed_signal_pairs": len(ordered),
        "reviewed_accounts": len({item.stable_user_id for item in ordered}),
        "reviewed_tokens": len(first),
        "semantics": _counts(item.semantic for item in ordered),
        "account_roles": _counts(item.account_role for item in ordered),
        "pairs_with_author_wallet_buy_before_post": sum(
            item.author_wallet_buys_before_post > 0 for item in ordered
        ),
        "pair_post_to_peak": _trajectory(ordered),
        "first_reviewed_post_per_token": _trajectory(first),
        "warning": (
            "This is a retrospective, selected set of market-qualified tokens; "
            "multiples are descriptive and are not a win rate, causation estimate, "
            "or deployable strategy result."
        ),
    }


def _trajectory(rows: tuple[ReviewedSignal, ...]) -> dict[str, object]:
    if not rows:
        return {
            "rows": 0, "at_least_2x": 0, "at_least_5x": 0,
            "within_1h": 0, "within_6h": 0, "within_24h": 0,
            "median_multiple": None, "median_hours_to_peak": None,
        }
    multiples = tuple(item.post_to_peak_multiple for item in rows)
    hours = tuple(Decimal(item.seconds_to_peak) / Decimal(3_600) for item in rows)
    return {
        "rows": len(rows),
        "at_least_2x": sum(value >= 2 for value in multiples),
        "at_least_5x": sum(value >= 5 for value in multiples),
        "within_1h": sum(value <= 1 for value in hours),
        "within_6h": sum(value <= 6 for value in hours),
        "within_24h": sum(value <= 24 for value in hours),
        "median_multiple": str(median(multiples)),
        "median_hours_to_peak": str(median(hours)),
    }


def _counts(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))
