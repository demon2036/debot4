import pytest

from debot4.v6.golden_dogs.x_signal import (
    XSignalEvidence,
    XSignalGrade,
    assess_x_signal,
)


def evidence(**changes) -> XSignalEvidence:
    values = {
        "stable_x_identity": True,
        "pre_peak_exact_ca_post": True,
        "rpc_clean_kol_buy_count": 1,
        "exact_author_wallet_buy_before_post_count": 0,
        "wallet_x_binding": False,
    }
    values.update(changes)
    return XSignalEvidence(**values)


def test_same_bound_wallet_buy_before_post_is_grade_a_without_repeat_rule() -> None:
    result = assess_x_signal(evidence(
        exact_author_wallet_buy_before_post_count=1, wallet_x_binding=True,
    ))
    assert result.grade is XSignalGrade.A
    assert result.structural_candidate is True


def test_other_kol_buy_and_post_only_are_separate_grades() -> None:
    assert assess_x_signal(evidence()).grade is XSignalGrade.B
    assert assess_x_signal(evidence(
        rpc_clean_kol_buy_count=0,
    )).grade is XSignalGrade.C


def test_wallet_binding_without_post_is_research_only_grade_d() -> None:
    result = assess_x_signal(evidence(
        pre_peak_exact_ca_post=False, rpc_clean_kol_buy_count=0,
        wallet_x_binding=True,
    ))
    assert result.grade is XSignalGrade.D
    assert result.structural_candidate is False


def test_non_independent_role_is_excluded_even_when_timing_looks_early() -> None:
    assert assess_x_signal(evidence(excluded_role=True)).grade is XSignalGrade.EXCLUDE


def test_author_buy_cannot_be_asserted_without_wallet_binding() -> None:
    with pytest.raises(ValueError, match="wallet/X binding"):
        evidence(exact_author_wallet_buy_before_post_count=1)
