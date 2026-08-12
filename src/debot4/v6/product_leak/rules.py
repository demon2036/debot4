"""Pure public-resource diff rules for product and code leaks."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from urllib.parse import urlsplit

from ..explosion import ExplosionCategory, ExplosionEvent


_RESOURCE_ID = re.compile(r"[a-z0-9][a-z0-9._-]{0,63}")
_HASH = re.compile(r"[0-9a-f]{64}")
_EVM_CA = re.compile(r"0x[a-f0-9]{40}")


@dataclass(frozen=True, slots=True)
class PublicResourceSnapshot:
    resource_id: str
    actor_id: str
    actor_role: str
    observed_at: datetime
    source_url: str
    evidence_hash: str
    terms: frozenset[str]
    token_addresses: frozenset[str] = frozenset()
    artifacts: frozenset[str] = frozenset()
    title: str = ""
    retrieved_url: str = ""

    def __post_init__(self) -> None:
        resource_id = self.resource_id.strip().casefold()
        observed = self.observed_at
        parsed = urlsplit(self.source_url)
        retrieved = urlsplit(self.retrieved_url or self.source_url)
        terms = frozenset(item.strip().casefold() for item in self.terms if item.strip())
        addresses = frozenset(item.strip().casefold() for item in self.token_addresses)
        artifacts = frozenset(item.strip() for item in self.artifacts if item.strip())
        if not _RESOURCE_ID.fullmatch(resource_id):
            raise ValueError("public resource ID is invalid")
        if not self.actor_id.strip() or not self.actor_role.strip():
            raise ValueError("public resource actor identity is incomplete")
        if observed.tzinfo is None or observed.utcoffset() is None:
            raise ValueError("public resource time must be timezone-aware")
        if parsed.scheme != "https" or not parsed.hostname or parsed.fragment:
            raise ValueError("public resource source URL must be HTTPS")
        if retrieved.scheme != "https" or not retrieved.hostname or retrieved.fragment:
            raise ValueError("public resource retrieved URL must be HTTPS")
        if not _HASH.fullmatch(self.evidence_hash):
            raise ValueError("public resource evidence hash is invalid")
        if any(not _EVM_CA.fullmatch(item) for item in addresses):
            raise ValueError("public resource token address is invalid")
        if len(terms) > 64 or len(addresses) > 256 or len(artifacts) > 5_000:
            raise ValueError("public resource semantic set exceeds its limit")
        object.__setattr__(self, "resource_id", resource_id)
        object.__setattr__(self, "observed_at", observed.astimezone(timezone.utc))
        object.__setattr__(self, "terms", terms)
        object.__setattr__(self, "token_addresses", addresses)
        object.__setattr__(self, "artifacts", artifacts)
        object.__setattr__(self, "title", self.title.strip()[:500])
        object.__setattr__(self, "retrieved_url", self.retrieved_url or self.source_url)

    def as_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "observed_at": self.observed_at.isoformat(),
            "source_url": self.source_url,
            "evidence_hash": self.evidence_hash,
            "terms": sorted(self.terms),
            "token_addresses": sorted(self.token_addresses),
            "artifacts": sorted(self.artifacts),
            "title": self.title,
            "retrieved_url": self.retrieved_url,
        }


def product_diff_events(
    previous: PublicResourceSnapshot,
    current: PublicResourceSnapshot,
) -> tuple[ExplosionEvent, ...]:
    if previous.resource_id != current.resource_id or previous.actor_id != current.actor_id:
        raise ValueError("resource snapshots refer to different identities")
    changes = (
        ("public_term_added", current.terms - previous.terms),
        ("public_ca_added", current.token_addresses - previous.token_addresses),
        ("public_artifact_added", current.artifacts - previous.artifacts),
    )
    events = [
        ExplosionEvent(
            category=ExplosionCategory.PRODUCT_LEAK,
            subtype=subtype,
            occurred_at=current.observed_at,
            first_seen_at=current.observed_at,
            subject=current.resource_id,
            actor_id=current.actor_id,
            actor_role=current.actor_role,
            source_url=current.source_url,
            evidence_hash=current.evidence_hash,
            previous={},
            current={"value": value},
            confidence="verified",
            token_address=value if subtype == "public_ca_added" else "",
        )
        for subtype, values in changes
        for value in sorted(values)
    ]
    if previous.title != current.title:
        events.append(ExplosionEvent(
            category=ExplosionCategory.PRODUCT_LEAK,
            subtype="public_title_changed",
            occurred_at=current.observed_at,
            first_seen_at=current.observed_at,
            subject=current.resource_id,
            actor_id=current.actor_id,
            actor_role=current.actor_role,
            source_url=current.source_url,
            evidence_hash=current.evidence_hash,
            previous={"value": previous.title},
            current={"value": current.title},
            confidence="verified",
        ))
    return tuple(events)
