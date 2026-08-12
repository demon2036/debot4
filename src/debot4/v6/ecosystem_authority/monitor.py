"""One-shot authority relationship monitor; scheduling stays outside."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from ..x import XProfileClient, XProfileObservation
from .diff import following_change_events
from .following import FollowingClient
from .models import AuthorityNode, FollowingSnapshot
from .store import JsonFollowingSnapshotStore


@dataclass(slots=True)
class AuthorityRelationshipMonitor:
    profiles: XProfileClient
    following: FollowingClient
    snapshots: JsonFollowingSnapshotStore
    events: ExplosionEventStore

    def poll(self, actor: AuthorityNode) -> tuple[ExplosionEvent, ...]:
        observation = self.profiles.fetch_observation(actor.handle)
        if observation.profile.user_id != actor.user_id:
            raise ValueError("authority actor stable identity mismatch")
        current = (
            self._verified_empty(actor, observation)
            if observation.following_count_verified and observation.profile.following == 0
            else self.following.fetch(actor)
        )
        previous = self.snapshots.load(actor.user_id)
        if previous is None:
            self.snapshots.save(current)
            return ()
        found = following_change_events(previous, current)
        for event in found:
            self.events.append(event)
        self.snapshots.save(current)
        return found

    @staticmethod
    def _verified_empty(
        actor: AuthorityNode,
        observation: XProfileObservation,
    ) -> FollowingSnapshot:
        return FollowingSnapshot.create(
            actor=actor,
            observed_at=observation.profile.fetched_at,
            source_url=observation.source_url,
            page_hashes=(observation.sha256,),
            following={},
        )
