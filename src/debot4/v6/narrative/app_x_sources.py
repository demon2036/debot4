"""Optional X egress and repost source assembly."""

from __future__ import annotations

from ..x import (
    FxEgressPool,
    FxJsonHttp,
    FxTwitterRepostMonitor,
    XRepostTarget,
)
from .actor_registry import DEFAULT_ACTOR_REGISTRY
from .settings import NarrativeSettings


def x_reposts(
    settings: NarrativeSettings, http: FxJsonHttp
) -> FxTwitterRepostMonitor | None:
    targets = tuple(
        XRepostTarget(actor.handle, registration.author_ids[0])
        for registration in DEFAULT_ACTOR_REGISTRY.registrations()
        if registration.author_ids
        for actor in (registration.actor,)
        if actor.monitor_reposts
    )
    if not targets:
        return None
    return FxTwitterRepostMonitor(
        targets,
        http=http,
        max_workers=settings.x_repost_workers,
    )


def x_egress(settings: NarrativeSettings) -> FxEgressPool | None:
    path = settings.x_egress_pool_file
    if path is None:
        return None
    return FxEgressPool.from_toml(
        path,
        location=settings.x_egress_location,
        max_attempts=settings.x_egress_attempts,
    )
