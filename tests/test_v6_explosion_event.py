from datetime import datetime, timedelta, timezone

import pytest

from debot4.v6.explosion import ExplosionCategory, ExplosionEvent, ExplosionEventStore


NOW = datetime(2026, 8, 12, 17, tzinfo=timezone.utc)


def _event() -> ExplosionEvent:
    return ExplosionEvent(
        category=ExplosionCategory.IDENTITY_CHANGE,
        subtype="avatar_changed",
        occurred_at=NOW - timedelta(milliseconds=42),
        first_seen_at=NOW,
        subject="@bot",
        actor_id="2085838061347217408",
        actor_role="official_product",
        source_url="https://api.fxtwitter.com/2/profile/bot?about_account=1",
        evidence_hash="a" * 64,
        previous={"avatar_url": "old"},
        current={"avatar_url": "new"},
        confidence="verified",
    )


def test_event_is_deterministic_and_never_buy_eligible() -> None:
    first = _event()
    second = _event()

    assert first.event_id == second.event_id
    assert first.buy_eligible is False
    assert first.as_public_dict()["category"] == "identity_change"


def test_event_rejects_future_occurrence_and_direct_buy() -> None:
    values = _event().as_public_dict()
    values.pop("event_id")
    values["category"] = ExplosionCategory.IDENTITY_CHANGE
    values["occurred_at"] = NOW + timedelta(seconds=1)
    values["first_seen_at"] = NOW
    values["buy_eligible"] = True

    with pytest.raises(ValueError):
        ExplosionEvent(**values)


def test_store_is_append_only_and_idempotent(tmp_path) -> None:
    with ExplosionEventStore(tmp_path / "events.sqlite3") as store:
        assert store.append(_event()) is True
        assert store.append(_event()) is False
        assert store.count() == 1
        assert store.recent()[0]["subject"] == "@bot"
