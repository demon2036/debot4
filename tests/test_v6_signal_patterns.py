from decimal import Decimal

from debot4.v6.golden_dogs.signal_patterns import (
    ReviewedSignal,
    summarize_reviewed_signals,
)


def signal(address: str, post_at: int, multiple: str, hours: int) -> ReviewedSignal:
    return ReviewedSignal(
        address=address,
        stable_user_id=str(post_at),
        post_at=post_at,
        seconds_to_peak=hours * 3_600,
        post_to_peak_multiple=Decimal(multiple),
        semantic="market_thesis",
        account_role="kol_candidate",
        author_wallet_buys_before_post=1 if post_at == 10 else 0,
    )


def test_summary_deduplicates_tokens_by_earliest_reviewed_post() -> None:
    address_a = "0x" + "a" * 40
    address_b = "0x" + "b" * 40
    result = summarize_reviewed_signals((
        signal(address_a, 20, "3", 2),
        signal(address_a, 10, "5", 8),
        signal(address_b, 30, "1.5", 30),
    ))

    assert result["reviewed_signal_pairs"] == 3
    assert result["reviewed_tokens"] == 2
    assert result["pairs_with_author_wallet_buy_before_post"] == 1
    assert result["pair_post_to_peak"]["at_least_2x"] == 2
    first = result["first_reviewed_post_per_token"]
    assert first["rows"] == 2
    assert first["at_least_5x"] == 1
    assert first["median_multiple"] == "3.25"


def test_empty_summary_never_invents_a_rate() -> None:
    result = summarize_reviewed_signals(())

    assert result["pair_post_to_peak"]["median_multiple"] is None
    assert "not a win rate" in result["warning"]
