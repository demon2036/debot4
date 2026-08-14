from decimal import Decimal

from debot4.v6.golden_dogs.models import Candle
from debot4.v6.golden_dogs.wallet_outcome import assess_wallet_buy_outcome


def candle(at: int, high: str) -> Candle:
    value = Decimal(high)
    return Candle(at, value, value, value, value, Decimal("1"))


def test_wallet_outcome_excludes_buy_candle_and_requires_fdv() -> None:
    result = assess_wallet_buy_outcome(
        buy_at=301,
        signal_at=90_000,
        buy_price_usd=Decimal("0.0004"),
        total_supply=Decimal("1000000000"),
        candles=(candle(300, "0.01"), candle(600, "0.0008"), candle(86_400, "0.0007")),
    )
    assert result.measurable is True
    assert result.hit is True
    assert result.peak_price_usd == Decimal("0.0008")


def test_wallet_outcome_waits_for_point_in_time_maturity() -> None:
    result = assess_wallet_buy_outcome(
        buy_at=10_000,
        signal_at=20_000,
        buy_price_usd=Decimal("1"),
        total_supply=Decimal("1000000"),
        candles=(),
    )
    assert result.mature_as_of_signal is False
    assert result.hit is None


def test_wallet_outcome_fails_closed_on_incomplete_market_history() -> None:
    result = assess_wallet_buy_outcome(
        buy_at=301,
        signal_at=90_000,
        buy_price_usd=Decimal("1"),
        total_supply=Decimal("1000000"),
        candles=(),
    )
    assert result.measurable is False
    assert result.reasons == ("post_buy_market_history_missing",)
