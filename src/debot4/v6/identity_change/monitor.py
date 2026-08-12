"""One-shot identity monitor; scheduling stays outside this module."""

from __future__ import annotations

from dataclasses import dataclass

from ..explosion import ExplosionEvent, ExplosionEventStore
from ..x import XProfileClient
from .diff import profile_change_events
from .media import ProfileMediaClient
from .models import ProfileSnapshot
from .store import JsonProfileSnapshotStore


@dataclass(slots=True)
class IdentityChangeMonitor:
    profiles: XProfileClient
    snapshots: JsonProfileSnapshotStore
    events: ExplosionEventStore
    media: ProfileMediaClient | None = None

    def poll(
        self,
        handle: str,
        *,
        actor_role: str,
        expected_user_id: str = "",
    ) -> tuple[ExplosionEvent, ...]:
        observation = self.profiles.fetch_observation(handle)
        if expected_user_id and observation.profile.user_id != expected_user_id:
            raise ValueError("profile stable identity does not match the target")
        previous = self.snapshots.load(observation.profile.handle)
        avatar_hash = self._media_hash_for(
            previous, "avatar", observation.profile.avatar_url,
        )
        banner_hash = self._media_hash_for(
            previous, "banner", observation.profile.banner_url,
        )
        current = ProfileSnapshot.from_observation(
            observation,
            avatar_sha256=avatar_hash,
            banner_sha256=banner_hash,
        )
        if previous is None:
            self.snapshots.save(current)
            return ()
        found = profile_change_events(previous, current, actor_role=actor_role)
        for event in found:
            self.events.append(event)
        self.snapshots.save(current)
        return found

    def _media_hash_for(
        self,
        previous: ProfileSnapshot | None,
        media_name: str,
        url: str,
    ) -> str:
        if previous is not None and previous.state.get(f"{media_name}_url") == url:
            retained = previous.state.get(f"{media_name}_sha256")
            if isinstance(retained, str) and retained:
                return retained
        return self._media_hash(url)

    def _media_hash(self, url: str) -> str:
        if self.media is None or not url:
            return ""
        try:
            return self.media.fetch(url).sha256
        except (RuntimeError, ValueError):
            return ""
