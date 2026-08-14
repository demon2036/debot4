from debot4.v6.golden_dogs.wallet_signal import (
    WalletSignalHistory,
    WalletSignalVerdict,
    assess_wallet_signal,
)


def history(**changes):
    values = {
        "wallet": "0x" + "a" * 40,
        "x_handle": "exact_x",
        "period_start": 1,
        "period_end_exclusive": 10 * 86_400 + 1,
        "unique_tokens_bought": 20,
        "buy_transactions": 25,
        "pre_peak_gold_hits": 5,
        "outcomes_complete": True,
        "activity_coverage_complete": True,
    }
    values.update(changes)
    return WalletSignalHistory(**values)


def test_profit_is_not_an_input_to_wallet_signal_quality() -> None:
    result = assess_wallet_signal(history())
    assert result.verdict is WalletSignalVerdict.CANDIDATE
    assert result.hit_rate == 0.25
    assert result.reasons == ("selective_early_hits:x_attributed",)


def test_indiscriminate_high_frequency_wallet_is_rejected() -> None:
    result = assess_wallet_signal(history(unique_tokens_bought=100, pre_peak_gold_hits=50))
    assert result.verdict is WalletSignalVerdict.REJECT
    assert result.reasons == ("indiscriminate_high_frequency_buyer",)


def test_wallet_can_rank_without_x_but_incomplete_denominator_cannot() -> None:
    anonymous = assess_wallet_signal(history(x_handle=None))
    assert anonymous.verdict is WalletSignalVerdict.CANDIDATE
    assert anonymous.reasons == ("selective_early_hits:anonymous_wallet",)
    assert assess_wallet_signal(
        history(activity_coverage_complete=False),
    ).verdict is WalletSignalVerdict.WAIT


def test_provider_manipulation_tag_rejects_before_incomplete_history_wait() -> None:
    result = assess_wallet_signal(history(
        provider_risk_tags=("gmgn", "sandwich_bot"),
        activity_coverage_complete=False,
        outcomes_complete=False,
    ))
    assert result.verdict is WalletSignalVerdict.REJECT
    assert result.reasons == ("provider_manipulation_tag:sandwich_bot",)
