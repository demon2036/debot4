import pytest

from debot4.v6.golden_dogs.x_wallet_timeline import (
    WalletPostTiming,
    classify_wallet_post_timing,
)


def test_buy_days_before_post_is_preserved_without_repetition_requirement() -> None:
    result = classify_wallet_post_timing(
        buy_at=1_000, post_at=1_000 + 4 * 86_400, peak_at=500_000,
    )
    assert result is WalletPostTiming.BUY_BEFORE_POST


def test_buy_after_post_is_separate_from_early_wallet_evidence() -> None:
    assert classify_wallet_post_timing(
        buy_at=200, post_at=100, peak_at=300,
    ) is WalletPostTiming.BUY_AFTER_POST_BEFORE_PEAK
    assert classify_wallet_post_timing(
        buy_at=300, post_at=100, peak_at=300,
    ) is WalletPostTiming.BUY_AFTER_PEAK


def test_post_peak_posts_cannot_enter_wallet_post_timeline() -> None:
    with pytest.raises(ValueError, match="pre-peak X post"):
        classify_wallet_post_timing(buy_at=100, post_at=300, peak_at=300)
