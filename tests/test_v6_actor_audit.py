from datetime import datetime, timezone

from debot4.v6.narrative.actor_audit import audit_actor_registry
from debot4.v6.narrative.actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from debot4.v6.x import XProfile


NOW = datetime(2026, 8, 10, 20, tzinfo=timezone.utc)


class FakeProfiles:
    def fetch(self, handle: str) -> XProfile:
        actor = DEFAULT_ACTOR_REGISTRY.resolve(handle)
        user_id = next(
            item.author_ids[0]
            for item in DEFAULT_ACTOR_REGISTRY.registrations()
            if item.actor == actor
        )
        if handle.casefold() == "sencrazy_1":
            user_id = "999999"
        return XProfile(handle, user_id, actor.display_name, actor.role, NOW)


def test_actor_audit_reports_verified_and_stable_id_mismatch() -> None:
    wanted = {"yeonwoo1102", "sencrazy_1"}
    registry = ActorRegistry(tuple(
        item for item in DEFAULT_ACTOR_REGISTRY.registrations()
        if item.actor.handle.casefold() in wanted
    ))

    report = audit_actor_registry(FakeProfiles(), registry, max_workers=2)

    assert report.verified_count == 1
    assert len(report.failures) == 1
    assert report.failures[0].handle == "Sencrazy_1"
    assert report.failures[0].status == "id_mismatch"
