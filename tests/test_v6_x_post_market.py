from decimal import Decimal

import pytest

from debot4.v6.golden_dogs.models import Candle
from debot4.v6.golden_dogs.x_post_market import assess_x_post_market


def candle(at: int, *, opening: str, high: str = "99") -> Candle:
    return Candle(
        at, Decimal(opening), Decimal(high), Decimal("0.1"),
        Decimal("88"), Decimal("1"),
    )


def test_post_reference_uses_causally_safe_minute_open_not_high_or_close() -> None:
    result = assess_x_post_market(
        (candle(60, opening="2"), candle(120, opening="4")),
        total_supply=Decimal("100"), post_at=158, peak_at=300,
        peak_fdv_usd=Decimal("2000"),
    )
    assert result.reference_at == 120
    assert result.reference_open_price_usd == Decimal("4")
    assert result.reference_fdv_usd == Decimal("400")
    assert result.post_to_peak_multiple == Decimal("5")
    assert result.seconds_to_peak == 142
    assert result.reference_age_seconds == 38


def test_future_candle_is_never_used_for_post_reference() -> None:
    result = assess_x_post_market(
        (candle(120, opening="3"), candle(180, opening="50")),
        total_supply=Decimal("10"), post_at=179, peak_at=240,
        peak_fdv_usd=Decimal("600"),
    )
    assert result.reference_at == 120
    assert result.reference_fdv_usd == Decimal("30")


def test_missing_or_stale_reference_is_not_treated_as_market_evidence() -> None:
    with pytest.raises(ValueError, match="no causal"):
        assess_x_post_market(
            (candle(180, opening="3"),), total_supply=Decimal("10"),
            post_at=179, peak_at=240, peak_fdv_usd=Decimal("600"),
        )
    with pytest.raises(ValueError, match="too stale"):
        assess_x_post_market(
            (candle(60, opening="3"),), total_supply=Decimal("10"),
            post_at=400, peak_at=500, peak_fdv_usd=Decimal("600"),
        )
