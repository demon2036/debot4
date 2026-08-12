from debot4.v6.golden_dogs.x_account_queue import (
    XAccountEvidence,
    XAccountRole,
    assess_x_account_queue,
)


def evidence(**changes):
    values = {
        "handle": "DeepTrader", "stable_user_id": "1234567",
        "display_name": "深大交易员", "source_kinds": ("verified_x_post",),
        "eligible_token_count": 4, "pre_peak_post_token_count": 2,
        "wallet_binding_pass": True, "provider_high_frequency": False,
    }
    values.update(changes)
    return XAccountEvidence(**values)


def test_verified_account_enters_monitor_queue_but_not_smart_wallet_ranking() -> None:
    result = assess_x_account_queue(evidence(), reviewed_role=XAccountRole.KOL_CANDIDATE)
    assert result.monitor_candidate is True
    assert result.smart_wallet_candidate is False
    assert "has_pre_peak_exact_ca_post" in result.reasons


def test_high_frequency_does_not_erase_x_identity() -> None:
    result = assess_x_account_queue(evidence(provider_high_frequency=True))
    assert result.monitor_candidate is True
    assert result.smart_wallet_candidate is False
    assert "high_frequency_excluded_from_wallet_signal" in result.reasons


def test_profile_only_grok_reference_does_not_enter_monitor_queue() -> None:
    result = assess_x_account_queue(evidence(
        source_kinds=("verified_x_profile",), eligible_token_count=0,
        pre_peak_post_token_count=0, wallet_binding_pass=False,
    ))
    assert result.monitor_candidate is False
    assert "insufficient_monitor_evidence" in result.reasons


def test_one_pre_peak_exact_ca_post_is_enough_without_repeat_requirement() -> None:
    result = assess_x_account_queue(evidence(
        eligible_token_count=1, pre_peak_post_token_count=1,
        wallet_binding_pass=False,
    ))
    assert result.monitor_candidate is True


def test_bound_wallet_and_reviewed_actor_are_independent_monitor_paths() -> None:
    wallet = assess_x_account_queue(evidence(
        eligible_token_count=0, pre_peak_post_token_count=0,
    ))
    reviewed = assess_x_account_queue(evidence(
        eligible_token_count=0, pre_peak_post_token_count=0,
        wallet_binding_pass=False,
    ), reviewed_role=XAccountRole.CATALYST)
    assert wallet.monitor_candidate is True
    assert reviewed.monitor_candidate is True


def test_non_independent_roles_are_not_kol_monitor_candidates() -> None:
    for role in (
        XAccountRole.SCANNER,
        XAccountRole.PROJECT,
        XAccountRole.COORDINATED_PROMOTION,
    ):
        assert assess_x_account_queue(
            evidence(), reviewed_role=role,
        ).monitor_candidate is False
