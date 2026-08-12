"""Immutable contract shared by every explosive-narrative monitor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import re
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlsplit


_HASH = re.compile(r"[0-9a-f]{64}")
_EVM_CA = re.compile(r"0x[a-f0-9]{40}")
_CONFIDENCE = frozenset({"verified", "corroborated", "reported", "unknown"})


class ExplosionCategory(str, Enum):
    IDENTITY_CHANGE = "identity_change"
    OWNERSHIP_CONFIRMATION = "ownership_confirmation"
    AUTHORITY_WALLET = "authority_wallet"
    PRODUCT_LEAK = "product_leak"
    REAL_WORLD_EVENT = "real_world_event"
    ECOSYSTEM_AUTHORITY = "ecosystem_authority"
    DISTRIBUTION_ACCESS = "distribution_access"
    RISK_RESOLUTION = "risk_resolution"
    CANONICAL_CA = "canonical_ca"


@dataclass(frozen=True, slots=True)
class ExplosionEvent:
    category: ExplosionCategory
    subtype: str
    occurred_at: datetime
    first_seen_at: datetime
    subject: str
    actor_id: str
    actor_role: str
    source_url: str
    evidence_hash: str
    previous: Mapping[str, object]
    current: Mapping[str, object]
    confidence: str = "unknown"
    chain: str = ""
    token_address: str = ""
    event_id: str = ""
    buy_eligible: bool = False

    def __post_init__(self) -> None:
        category = ExplosionCategory(self.category)
        occurred = _utc(self.occurred_at, "occurred_at")
        seen = _utc(self.first_seen_at, "first_seen_at")
        if occurred > seen:
            raise ValueError("explosion event occurred after it was first seen")
        if not all((self.subtype.strip(), self.subject.strip(), self.actor_id.strip())):
            raise ValueError("explosion event identity is incomplete")
        if not _https_url(self.source_url) or not _HASH.fullmatch(self.evidence_hash):
            raise ValueError("explosion event evidence receipt is invalid")
        confidence = self.confidence.strip().casefold()
        if confidence not in _CONFIDENCE:
            raise ValueError("unsupported explosion confidence")
        address = self.token_address.strip().casefold()
        if address and not _EVM_CA.fullmatch(address):
            raise ValueError("invalid explosion token address")
        if self.buy_eligible:
            raise ValueError("explosion evidence cannot be buy eligible")
        previous = _freeze(self.previous)
        current = _freeze(self.current)
        expected = _event_id(
            category, self.subtype, occurred, self.subject, self.actor_id,
            self.source_url, self.evidence_hash, previous, current, self.chain, address,
        )
        if self.event_id and self.event_id != expected:
            raise ValueError("explosion event ID does not match its content")
        object.__setattr__(self, "category", category)
        object.__setattr__(self, "subtype", self.subtype.strip().casefold())
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "first_seen_at", seen)
        object.__setattr__(self, "subject", self.subject.strip())
        object.__setattr__(self, "actor_id", self.actor_id.strip())
        object.__setattr__(self, "actor_role", self.actor_role.strip())
        object.__setattr__(self, "confidence", confidence)
        object.__setattr__(self, "chain", self.chain.strip().casefold())
        object.__setattr__(self, "token_address", address)
        object.__setattr__(self, "previous", previous)
        object.__setattr__(self, "current", current)
        object.__setattr__(self, "event_id", expected)
        object.__setattr__(self, "buy_eligible", False)

    def as_public_dict(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "category": self.category.value,
            "subtype": self.subtype,
            "occurred_at": self.occurred_at.isoformat(),
            "first_seen_at": self.first_seen_at.isoformat(),
            "subject": self.subject,
            "actor_id": self.actor_id,
            "actor_role": self.actor_role,
            "source_url": self.source_url,
            "evidence_hash": self.evidence_hash,
            "previous": dict(self.previous),
            "current": dict(self.current),
            "confidence": self.confidence,
            "chain": self.chain,
            "token_address": self.token_address,
            "buy_eligible": False,
        }


def _event_id(
    category: ExplosionCategory, subtype: str, occurred: datetime,
    subject: str, actor_id: str, source_url: str, evidence_hash: str,
    previous: Mapping[str, object], current: Mapping[str, object],
    chain: str, token_address: str,
) -> str:
    payload = {
        "category": category.value,
        "subtype": subtype.strip().casefold(),
        "occurred_at": occurred.isoformat(),
        "subject": subject.strip(),
        "actor_id": actor_id.strip(),
        "source_url": source_url,
        "evidence_hash": evidence_hash,
        "previous": dict(previous),
        "current": dict(current),
        "chain": chain.strip().casefold(),
        "token_address": token_address,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _freeze(value: Mapping[str, object]) -> Mapping[str, object]:
    clean: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError("explosion state must be a flat JSON object")
        clean[key] = item
    return MappingProxyType(clean)


def _utc(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)
