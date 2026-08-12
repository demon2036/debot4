"""Pure profile diff rules that emit one auditable event per changed field."""

from __future__ import annotations

from datetime import datetime

from ..explosion import ExplosionCategory, ExplosionEvent
from .models import ProfileSnapshot
from .timestamps import profile_resource_time


_TRACKED = (
    "display_name", "description", "avatar_url", "banner_url", "location",
    "profile_url", "website_url", "website_display", "verified",
    "verification_type", "protected", "based_in", "username_change_count",
    "username_changed_at",
)
_MEDIA_HASHES = ("avatar_sha256", "banner_sha256")


def profile_change_events(
    previous: ProfileSnapshot,
    current: ProfileSnapshot,
    *,
    actor_role: str,
) -> tuple[ExplosionEvent, ...]:
    if previous.handle != current.handle:
        raise ValueError("profile snapshots belong to different handles")
    events: list[ExplosionEvent] = []
    if previous.user_id != current.user_id:
        events.append(_event(
            current, "stable_identity_changed", actor_role,
            {"user_id": previous.user_id}, {"user_id": current.user_id},
            current.observed_at,
        ))
    for field_name in _TRACKED:
        old = previous.state.get(field_name)
        new = current.state.get(field_name)
        if old == new:
            continue
        occurred = _resource_time(field_name, new, current.observed_at)
        events.append(_event(
            current, f"{field_name}_changed", actor_role,
            {field_name: old}, {field_name: new}, occurred,
        ))
    for field_name in _MEDIA_HASHES:
        old = previous.state.get(field_name)
        new = current.state.get(field_name)
        if not old or not new or old == new:
            continue
        media = field_name.removesuffix("_sha256")
        events.append(_event(
            current, f"{media}_content_changed", actor_role,
            {field_name: old}, {field_name: new}, current.observed_at,
            evidence_hash=str(new),
        ))
    return tuple(events)


def _event(
    current: ProfileSnapshot,
    subtype: str,
    role: str,
    previous: dict[str, object],
    new: dict[str, object],
    occurred_at: datetime,
    *,
    evidence_hash: str | None = None,
) -> ExplosionEvent:
    return ExplosionEvent(
        category=ExplosionCategory.IDENTITY_CHANGE,
        subtype=subtype,
        occurred_at=occurred_at,
        first_seen_at=current.observed_at,
        subject=f"@{current.handle}",
        actor_id=current.user_id,
        actor_role=role,
        source_url=current.source_url,
        evidence_hash=evidence_hash or current.evidence_hash,
        previous=previous,
        current=new,
        confidence="verified",
    )


def _resource_time(field_name: str, value: object, seen: datetime) -> datetime:
    if field_name not in {"avatar_url", "banner_url"} or not isinstance(value, str):
        return seen
    inferred = profile_resource_time(value)
    return inferred if inferred is not None and inferred <= seen else seen
