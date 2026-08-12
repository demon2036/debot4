"""One-shot authority relationship monitor; scheduling stays outside."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from ..x import XProfileClient
from .diff import following_change_events
from .following import FollowingClient
from .models import AuthorityNode
from .store import JsonFollowingSnapshotStore


@dataclass(slots=True)
class AuthorityRelationshipMonitor:
    profiles: XProfileClient
    following: FollowingClient
    snapshots: JsonFollowingSnapshotStore
    events: ExplosionEventStore

    def poll(self, actor: AuthorityNode) -> tuple[ExplosionEvent, ...]:
        profile = self.profiles.fetch(actor.handle)
        if profile.user_id != actor.user_id:
            raise ValueError("authority actor stable identity mismatch")
        current = self.following.fetch(actor)
        previous = self.snapshots.load(actor.user_id)
        if previous is None:
            self.snapshots.save(current)
            return ()
        found = following_change_events(previous, current)
        for event in found:
            self.events.append(event)
        self.snapshots.save(current)
        return found
