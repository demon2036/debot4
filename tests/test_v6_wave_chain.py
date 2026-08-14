from decimal import Decimal

import pytest

from debot4.v6.golden_dogs.wave_chain import ChainBuy, summarize_chain_activity


def _buy(timestamp: int, suffix: str, *, clean: bool, amount: str = "1") -> ChainBuy:
    return ChainBuy(
        timestamp=timestamp,
        transaction_hash=f"0x{suffix}",
        wallet=f"0xwallet{suffix}",
        amount_usd=Decimal(amount),
        x_handle=None,
        tags=("kol",),
        rpc_receipt_sha256="a" * 64,
        clean=clean,
    )


def test_summary_uses_half_open_bounds_and_separates_clean_buys() -> None:
    result = summarize_chain_activity(
        (_buy(9, "0", clean=True), _buy(10, "1", clean=False),
         _buy(11, "2", clean=True, amount="4"), _buy(12, "3", clean=True)),
        10,
        12,
    )

    assert result.tagged_buy_count == 2
    assert result.clean_buy_count == 1
    assert result.earliest_tagged and result.earliest_tagged.timestamp == 10
    assert result.earliest_clean and result.earliest_clean.timestamp == 11
    assert result.clean_amount_usd == Decimal("4")


def test_summary_deduplicates_wallets_case_insensitively() -> None:
    first = _buy(10, "1", clean=True)
    second = ChainBuy(
        timestamp=11,
        transaction_hash="0x2",
        wallet=first.wallet.upper().replace("0X", "0x"),
        amount_usd=Decimal("2"),
        x_handle="handle",
        tags=(),
        rpc_receipt_sha256="b" * 64,
        clean=True,
    )

    result = summarize_chain_activity((first, second), 10, 20)

    assert result.tagged_wallet_count == 1
    assert result.clean_wallet_count == 1
    assert result.largest_clean == second


def test_summary_rejects_invalid_interval() -> None:
    with pytest.raises(ValueError):
        summarize_chain_activity((), 10, 10)
