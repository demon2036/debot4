from decimal import Decimal
import pytest

from debot4.v6.golden_dogs.gmgn_market_trades import GmgnMarketTrade
from debot4.v6.golden_dogs.trade_price_timing import (
    TransactionPriceCrossing,
    TradeSignalStage,
    classify_trade_signal,
    find_transaction_price_crossing,
    strictly_precedes_crossing,
)


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40


def trade(at: int, price: str, digit: str, sequence: int | None):
    return GmgnMarketTrade(
        WALLET, CA, "buy", at, Decimal("1"), Decimal("1"), Decimal(price),
        "0x" + digit * 64, "", None, (), (), (), sequence,
    )


def test_transaction_price_crossing_refines_same_minute_order() -> None:
    before = trade(101, "11", "1", 1010)
    same_second_before = trade(102, "11.5", "2", 1020)
    crossed = trade(102, "12", "3", 1030)
    after = trade(103, "13", "4", 1040)
    crossing = find_transaction_price_crossing(
        (after, crossed, before, same_second_before), Decimal("12"),
    )
    assert crossing is not None
    assert crossing.occurred_at == 102
    assert crossing.same_second_trade_count == 2
    assert classify_trade_signal(
        before, crossing, baseline_established_at=100,
    ).stage == TradeSignalStage.STRICT_PRE_MOTION
    timing = classify_trade_signal(
        same_second_before, crossing, baseline_established_at=100,
    )
    assert timing.strict_advance is True
    assert timing.sequence_gap == 10
    assert classify_trade_signal(
        after, crossing, baseline_established_at=100,
    ).stage == TradeSignalStage.AFTER_MOTION


def test_missing_same_second_sequence_remains_ambiguous() -> None:
    unknown = trade(102, "11", "1", None)
    crossed = trade(102, "12", "2", 1030)
    crossing = find_transaction_price_crossing((unknown, crossed), Decimal("12"))
    assert crossing is not None
    timing = classify_trade_signal(unknown, crossing, baseline_established_at=100)
    assert timing.stage == TradeSignalStage.CROSSING_SECOND_AMBIGUOUS
    assert timing.strict_advance is False


def test_pre_baseline_trade_does_not_become_advance_by_hindsight() -> None:
    early = trade(99, "9", "1", 990)
    crossed = trade(102, "12", "2", 1020)
    crossing = find_transaction_price_crossing((early, crossed), Decimal("12"))
    result = classify_trade_signal(early, crossing, baseline_established_at=100)
    assert result.stage == TradeSignalStage.BEFORE_BASELINE_KNOWN
    assert result.strict_advance is False


def test_crossing_ignores_old_high_before_baseline_was_known() -> None:
    old_high = trade(99, "13", "1", 990)
    trough = trade(100, "10", "2", 1000)
    crossed = trade(105, "12", "3", 1050)
    crossing = find_transaction_price_crossing(
        (old_high, trough, crossed), Decimal("12"), not_before=100,
    )
    assert crossing is not None
    assert crossing.transaction_hash == crossed.transaction_hash


def test_crossing_start_must_be_positive() -> None:
    with pytest.raises(ValueError, match="start"):
        find_transaction_price_crossing((), Decimal("12"), not_before=0)


def test_serialized_event_order_is_conservative_in_crossing_second() -> None:
    crossing = TransactionPriceCrossing(
        Decimal("12"), 102, 30, "0x" + "1" * 64, 2, True,
    )
    assert strictly_precedes_crossing(101, None, crossing) is True
    assert strictly_precedes_crossing(102, 20, crossing) is True
    assert strictly_precedes_crossing(102, None, crossing) is False
    assert strictly_precedes_crossing(103, 10, crossing) is False
    with pytest.raises(ValueError, match="event time"):
        strictly_precedes_crossing(0, 10, crossing)
