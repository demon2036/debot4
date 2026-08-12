"""Persistable identity state separated from volatile audience counters."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from types import MappingProxyType
from typing import Mapping

from ..x import XCheckpoint, XProfile, XProfileObservation


_HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class ProfileSnapshot:
    handle: str
    user_id: str
    observed_at: datetime
    source_url: str
    evidence_hash: str
    state: Mapping[str, object]

    def __post_init__(self) -> None:
        observed = self.observed_at
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("profile snapshot time must be timezone-aware")
        handle = XCheckpoint(self.handle, self.user_id).handle
        if not _HASH.fullmatch(self.evidence_hash):
            raise ValueError("profile snapshot identity or evidence is invalid")
        clean = dict(self.state)
        if any(not isinstance(key, str) for key in clean):
            raise ValueError("profile snapshot keys must be strings")
        if any(not isinstance(value, (str, int, bool, type(None))) for value in clean.values()):
            raise ValueError("profile snapshot values must be scalar")
        object.__setattr__(self, "observed_at", observed.astimezone(timezone.utc))
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "state", MappingProxyType(clean))

    @classmethod
    def from_observation(
        cls,
        observation: XProfileObservation,
        *,
        avatar_sha256: str = "",
        banner_sha256: str = "",
    ) -> "ProfileSnapshot":
        profile = observation.profile
        return cls(
            profile.handle,
            profile.user_id,
            profile.fetched_at,
            observation.source_url,
            observation.sha256,
            _identity_state(profile, avatar_sha256, banner_sha256),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "handle": self.handle,
            "user_id": self.user_id,
            "observed_at": self.observed_at.isoformat(),
            "source_url": self.source_url,
            "evidence_hash": self.evidence_hash,
            "state": dict(self.state),
        }


def _identity_state(
    profile: XProfile, avatar_sha256: str, banner_sha256: str,
) -> dict[str, object]:
    for value in (avatar_sha256, banner_sha256):
        if value and not _HASH.fullmatch(value):
            raise ValueError("profile media hash is invalid")
    return {
        "display_name": profile.display_name,
        "description": profile.description,
        "avatar_url": profile.avatar_url,
        "avatar_sha256": avatar_sha256,
        "banner_url": profile.banner_url,
        "banner_sha256": banner_sha256,
        "location": profile.location,
        "profile_url": profile.profile_url,
        "website_url": profile.website_url,
        "website_display": profile.website_display,
        "verified": profile.verified,
        "verification_type": profile.verification_type,
        "protected": profile.protected,
        "based_in": profile.based_in,
        "username_change_count": profile.username_change_count,
        "username_changed_at": profile.username_changed_at,
    }
