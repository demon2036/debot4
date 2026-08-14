import pytest

from debot4.v6.golden_dogs.event_time_capture import (
    AdvanceFreshness,
    AdvanceLane,
    LEAD_TIME_BUCKETS,
    PublicAdvanceEvent,
    assess_public_event_time,
    lead_time_bucket,
)


def event(**changes):
    values = {
        "source": "x", "event_id": "x:1", "occurred_at": 150,
        "lane": AdvanceLane.INDEPENDENT, "exact_ca_bound": True,
        "semantically_forward": True,
    }
    values.update(changes)
    return PublicAdvanceEvent(**values)


def test_fresh_event_before_small_move_is_event_time_ceiling() -> None:
    result = assess_public_event_time(
        event(), fresh_start=100, first_1_02_at=200,
        assumed_latency_seconds=5,
    )
    assert result.event_time_actionable
    assert result.source == "x"
    assert result.freshness is AdvanceFreshness.FRESH
    assert result.seconds_to_first_1_02 == 45


def test_older_event_is_standing_not_fresh_trigger() -> None:
    result = assess_public_event_time(
        event(occurred_at=50), fresh_start=100, first_1_02_at=200,
        assumed_latency_seconds=5,
    )
    assert result.event_time_actionable
    assert result.freshness is AdvanceFreshness.STANDING


@pytest.mark.parametrize("changes,reason", [
    ({"exact_ca_bound": False}, "exact_ca_unresolved"),
    ({"semantically_forward": False}, "not_forward_semantic"),
    ({"occurred_at": 199}, "not_before_first_1_02"),
])
def test_hard_gates_exclude_non_advance(changes, reason) -> None:
    result = assess_public_event_time(
        event(**changes), fresh_start=100, first_1_02_at=200,
        assumed_latency_seconds=1,
    )
    assert not result.event_time_actionable
    assert reason in result.reasons


def test_invalid_latency_is_rejected() -> None:
    with pytest.raises(ValueError, match="latency"):
        assess_public_event_time(
            event(), fresh_start=100, first_1_02_at=200,
            assumed_latency_seconds=-1,
        )


@pytest.mark.parametrize("seconds,expected", [
    (1, "lt_60s"), (60, "60s_to_lt_300s"),
    (300, "300s_to_lt_1800s"), (1_800, "1800s_to_lt_21600s"),
    (21_600, "21600s_to_lt_86400s"), (86_400, "gte_86400s"),
])
def test_lead_time_buckets_have_explicit_boundaries(seconds, expected) -> None:
    assert lead_time_bucket(seconds) == expected
    assert expected in LEAD_TIME_BUCKETS


@pytest.mark.parametrize("seconds", [0, -1, True, 1.2])
def test_invalid_lead_time_is_rejected(seconds) -> None:
    with pytest.raises(ValueError, match="lead seconds"):
        lead_time_bucket(seconds)
