"""Pure following-relationship diff rules."""

from __future__ import annotations

from ..explosion import ExplosionCategory, ExplosionEvent
from .models import FollowingSnapshot


def following_change_events(
    previous: FollowingSnapshot,
    current: FollowingSnapshot,
) -> tuple[ExplosionEvent, ...]:
    if previous.actor.user_id != current.actor.user_id:
        raise ValueError("following snapshots belong to different actors")
    events: list[ExplosionEvent] = []
    previous_ids = set(previous.following)
    current_ids = set(current.following)
    for user_id in sorted(current_ids - previous_ids):
        events.append(_event(current, "authority_follow_added", user_id, "", current.following[user_id]))
    for user_id in sorted(previous_ids - current_ids):
        events.append(_event(current, "authority_follow_removed", user_id, previous.following[user_id], ""))
    return tuple(events)


def _event(
    current: FollowingSnapshot,
    subtype: str,
    target_id: str,
    previous_handle: str,
    current_handle: str,
) -> ExplosionEvent:
    target = current_handle or previous_handle
    return ExplosionEvent(
        category=ExplosionCategory.ECOSYSTEM_AUTHORITY,
        subtype=subtype,
        occurred_at=current.observed_at,
        first_seen_at=current.observed_at,
        subject=f"@{current.actor.handle} -> @{target}",
        actor_id=current.actor.user_id,
        actor_role=current.actor.role,
        source_url=current.source_url,
        evidence_hash=current.evidence_hash,
        previous={"target_user_id": target_id, "target_handle": previous_handle},
        current={"target_user_id": target_id, "target_handle": current_handle},
        confidence="verified",
    )
