from decimal import Decimal
import pytest

from debot4.v6.golden_dogs.gmgn_market_trades import GmgnMarketTrade
from debot4.v6.golden_dogs.trade_microstructure import (
    find_price_ladder,
    summarize_pre_crossing_buy_flow,
)


CA = "0x" + "a" * 40


def trade(at, price, digit, sequence, wallet_digit="b", amount="10"):
    return GmgnMarketTrade(
        "0x" + wallet_digit * 40, CA, "buy", at, Decimal("1"), Decimal(amount),
        Decimal(price), "0x" + digit * 64, "", None, (), (), (), sequence,
    )


def test_price_ladder_preserves_transaction_order_and_missing_steps() -> None:
    rows = (
        trade(101, "10.2", "1", 10),
        trade(102, "11", "2", 20),
        trade(103, "12", "3", 30),
    )
    ladder = find_price_ladder(
        rows, Decimal("10"), baseline_established_at=100,
    )
    assert [step.crossing.occurred_at if step.crossing else None for step in ladder] == [
        101, 102, 102, 103,
    ]


def test_buy_flow_counts_strict_same_second_order_and_wallet_burst() -> None:
    rows = (
        trade(100, "10", "1", 10, amount="5"),
        trade(101, "10.5", "2", 20, amount="7"),
        trade(102, "11", "3", 30, amount="8"),
        trade(103, "11.5", "4", 40, wallet_digit="c", amount="20"),
        trade(103, "12", "5", 50, wallet_digit="d", amount="1"),
    )
    crossing = find_price_ladder(
        rows, Decimal("10"), baseline_established_at=100,
    )[-1].crossing
    assert crossing is not None
    whole = summarize_pre_crossing_buy_flow(
        rows, crossing, baseline_established_at=100,
    )[-1]
    assert whole.buy_count == 4
    assert whole.unique_wallet_count == 2
    assert whole.gross_buy_usd == Decimal("40")
    assert whole.repeat_wallet_count == 1
    assert whole.burst_wallet_count == 1
    assert whole.largest_wallet_buy_count == 3
    assert whole.largest_wallet_gross_buy_usd == Decimal("20")


def test_microstructure_rejects_invalid_rules() -> None:
    with pytest.raises(ValueError, match="multiples"):
        find_price_ladder(
            (), Decimal("1"), baseline_established_at=1,
            multiples=(Decimal("1.2"), Decimal("1.1")),
        )
