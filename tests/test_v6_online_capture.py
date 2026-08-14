import pytest

from debot4.v6.golden_dogs.online_capture import (
    CaptureKind,
    assess_early_motion,
    assess_exogenous_signal,
    assess_onchain_candidate,
    combine_capture_lanes,
)


def test_public_signal_requires_seen_time_semantics_and_exact_ca() -> None:
    result = assess_exogenous_signal(
        100, 105, 120, semantically_qualified=True, exact_ca_bound=True,
    )
    assert result.kind == CaptureKind.EXOGENOUS_ADVANCE
    assert result.seconds_to_motion == 15
    rejected = assess_exogenous_signal(
        100, 105, 120, semantically_qualified=False, exact_ca_bound=True,
    )
    assert rejected.actionable is False


def test_onchain_candidate_requires_prior_block_latency_and_as_of_skill() -> None:
    result = assess_onchain_candidate(
        100, 103, 120, prior_block=True,
        observation_latency_seconds=5, as_of_qualified=True,
    )
    assert result.kind == CaptureKind.ONCHAIN_ADVANCE_CANDIDATE
    assert result.seconds_to_motion == 12
    rejected = assess_onchain_candidate(
        100, 103, 120, prior_block=False,
        observation_latency_seconds=5, as_of_qualified=False,
    )
    assert set(rejected.reasons) == {
        "same_block_or_later", "wallet_or_kol_not_qualified_as_of_signal",
    }


def test_small_move_is_early_detection_and_must_leave_latency_budget() -> None:
    result = assess_early_motion(100, 120, observation_latency_seconds=5)
    assert result.kind == CaptureKind.EARLY_MOTION
    assert result.seconds_to_motion == 15
    assert assess_early_motion(
        100, 105, observation_latency_seconds=5,
    ).actionable is False


def test_seen_time_cannot_predate_occurrence() -> None:
    with pytest.raises(ValueError, match="first seen"):
        assess_exogenous_signal(
            100, 99, 120, semantically_qualified=True, exact_ca_bound=True,
        )


def test_combiner_keeps_unqualified_wallet_as_timing_ceiling_only() -> None:
    provider = assess_onchain_candidate(
        100, 100, 120, prior_block=True,
        observation_latency_seconds=5, as_of_qualified=False,
    )
    result = combine_capture_lanes(
        ((False, False),), (provider,), assess_early_motion(
            110, 120, observation_latency_seconds=5,
        ),
    )
    assert result.provider_timing_ceiling is True
    assert result.qualified_provider_advance is False
    assert result.timing_union_ceiling is True
    assert result.semantic_public_or_qualified_provider_advance is False
    assert result.early_motion_detection is True


def test_public_lane_can_be_fresh_and_qualified_without_wallet_upgrade() -> None:
    result = combine_capture_lanes(
        ((True, True),), (), assess_early_motion(
            None, None, observation_latency_seconds=0,
        ),
    )
    assert result.public_advance is True
    assert result.fresh_public_advance is True
    assert result.semantic_public_or_qualified_provider_advance is True
    assert result.provider_timing_ceiling is False
