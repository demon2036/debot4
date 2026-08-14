import pytest

from debot4.v6.golden_dogs.advance_actor import summarize_advance_actors


def event(**changes):
    row = {
        "source": "x", "actor": "Alpha", "label": "DOG",
        "wave_number": 1, "occurred_at": 100, "lead_seconds": 30,
        "url": "https://x.com/i/status/1",
    }
    row.update(changes)
    return row


def test_actor_summary_deduplicates_wave_coverage_and_preserves_events() -> None:
    rows = summarize_advance_actors([
        event(), event(occurred_at=101, lead_seconds=29),
        event(label="CAT", wave_number=2, occurred_at=90, lead_seconds=50),
    ])
    assert len(rows) == 1
    assert rows[0]["advance_event_count"] == 3
    assert rows[0]["advance_wave_count"] == 2
    assert rows[0]["target_count"] == 2
    assert rows[0]["fresh_advance_wave_count"] == 0
    assert rows[0]["closest_lead_seconds"] == 29
    assert rows[0]["closest_event"]["occurred_at"] == 101
    assert rows[0]["qualification_status"] == "discovery_lead_only"


def test_fresh_coverage_does_not_promote_standing_replays() -> None:
    rows = summarize_advance_actors([
        event(freshness="fresh_pre_motion"),
        event(wave_number=2, freshness="standing_pre_wave"),
    ])
    assert rows[0]["advance_wave_count"] == 2
    assert rows[0]["fresh_advance_wave_count"] == 1


def test_sources_and_casefolded_actors_are_stable_boundaries() -> None:
    rows = summarize_advance_actors([
        event(actor="ALPHA"), event(actor="alpha", wave_number=2),
        event(source="telegram", actor="alpha"),
    ])
    assert len(rows) == 2
    assert rows[0]["advance_wave_count"] == 2


@pytest.mark.parametrize("changes", [
    {"actor": ""}, {"label": ""}, {"wave_number": 0}, {"lead_seconds": 0},
])
def test_invalid_actor_events_fail_closed(changes) -> None:
    with pytest.raises(ValueError):
        summarize_advance_actors([event(**changes)])
