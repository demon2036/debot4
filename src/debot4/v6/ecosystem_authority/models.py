"""Immutable X authority-relationship snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit

from ..x import XCheckpoint


_HASH = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class AuthorityNode:
    handle: str
    user_id: str
    display_name: str
    role: str
    evidence_url: str

    def __post_init__(self) -> None:
        handle = XCheckpoint(self.handle, self.user_id).handle
        if not self.display_name.strip() or not self.role.strip():
            raise ValueError("authority node requires a name and role")
        if not _https(self.evidence_url):
            raise ValueError("authority node evidence URL must use HTTPS")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "role", self.role.strip())


@dataclass(frozen=True, slots=True)
class FollowingSnapshot:
    actor: AuthorityNode
    observed_at: datetime
    source_url: str
    evidence_hash: str
    following: Mapping[str, str]
    page_count: int

    def __post_init__(self) -> None:
        observed = _utc(self.observed_at)
        if not _https(self.source_url) or not _HASH.fullmatch(self.evidence_hash):
            raise ValueError("following snapshot evidence is invalid")
        if isinstance(self.page_count, bool) or not 1 <= self.page_count <= 100:
            raise ValueError("following snapshot page count is invalid")
        clean: dict[str, str] = {}
        for user_id, handle in self.following.items():
            checkpoint = XCheckpoint(str(handle), str(user_id))
            if checkpoint.user_id in clean:
                raise ValueError("duplicate following stable identity")
            clean[checkpoint.user_id] = checkpoint.handle
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "following", MappingProxyType(clean))

    @classmethod
    def create(
        cls,
        *,
        actor: AuthorityNode,
        observed_at: datetime,
        source_url: str,
        page_hashes: tuple[str, ...],
        following: Mapping[str, str],
    ) -> "FollowingSnapshot":
        if not page_hashes or any(not _HASH.fullmatch(item) for item in page_hashes):
            raise ValueError("following page receipts are invalid")
        raw = json.dumps(page_hashes, separators=(",", ":")).encode()
        return cls(
            actor=actor,
            observed_at=observed_at,
            source_url=source_url,
            evidence_hash=hashlib.sha256(raw).hexdigest(),
            following=following,
            page_count=len(page_hashes),
        )

    def as_dict(self) -> dict[str, object]:
        return {
            "actor": {
                "handle": self.actor.handle,
                "user_id": self.actor.user_id,
                "display_name": self.actor.display_name,
                "role": self.actor.role,
                "evidence_url": self.actor.evidence_url,
            },
            "observed_at": self.observed_at.isoformat(),
            "source_url": self.source_url,
            "evidence_hash": self.evidence_hash,
            "following": dict(self.following),
            "page_count": self.page_count,
        }


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("following snapshot time must be timezone-aware")
    return value.astimezone(timezone.utc)


def _https(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)
