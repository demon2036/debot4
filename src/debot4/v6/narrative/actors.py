"""Auditable actor tiers used by narrative investigations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from urllib.parse import urlsplit


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,32}")


class ActorTier(str, Enum):
    GLOBAL_AGENDA = "global_agenda"
    ECOSYSTEM_AUTHORITY = "ecosystem_authority"
    ORIGINAL_CREATOR = "original_creator"
    DOMAIN_EXPERT = "domain_expert"
    PROPAGATION_KOL = "propagation_kol"
    UNKNOWN = "unknown"


class ActorCapability(str, Enum):
    ESTABLISH_ORIGIN = "establish_origin"
    CREATE_CATALYST = "create_catalyst"
    BIND_CA = "bind_ca"
    AUTHORITATIVE_COUNTER = "authoritative_counter"
    PROPAGATE = "propagate"


@dataclass(frozen=True, slots=True)
class ActorRef:
    """A stable actor identity whose tier has an explicit verification basis."""

    actor_id: str
    handle: str
    tier: ActorTier
    tier_basis: str
    ecosystems: tuple[str, ...] = ()
    capabilities: tuple[ActorCapability, ...] = ()
    display_name: str = ""
    role: str = ""
    languages: tuple[str, ...] = ()
    regions: tuple[str, ...] = ()
    telegram_channels: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()
    priority: int = 50
    risk_notes: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    monitor_x: bool = True
    monitor_reposts: bool = False
    telegram_public_channels: tuple[str, ...] = ()
    telegram_realtime_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        actor_id = self.actor_id.strip()
        handle = self.handle.strip().lstrip("@")
        basis = self.tier_basis.strip()
        tier = ActorTier(self.tier)
        ecosystems = tuple(dict.fromkeys(
            item.strip().casefold() for item in self.ecosystems if item.strip()
        ))
        capabilities = tuple(dict.fromkeys(
            ActorCapability(item) for item in self.capabilities
        ))
        evidence_urls = _clean(self.evidence_urls)
        if not actor_id or not _HANDLE.fullmatch(handle):
            raise ValueError("stable actor_id and valid handle are required")
        if tier is not ActorTier.UNKNOWN and not basis:
            raise ValueError("known actor tiers require a verification basis")
        if not 1 <= self.priority <= 100:
            raise ValueError("actor priority must be between 1 and 100")
        if any(not _https_url(item) for item in evidence_urls):
            raise ValueError("actor evidence URLs must use HTTPS")
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "tier", tier)
        object.__setattr__(self, "tier_basis", basis)
        object.__setattr__(self, "ecosystems", ecosystems)
        object.__setattr__(self, "capabilities", capabilities)
        object.__setattr__(self, "display_name", self.display_name.strip())
        object.__setattr__(self, "role", self.role.strip())
        object.__setattr__(self, "languages", _clean(self.languages))
        object.__setattr__(self, "regions", _clean(self.regions))
        object.__setattr__(self, "telegram_channels", _clean(self.telegram_channels))
        public_channels = _clean(self.telegram_public_channels)
        if not set(public_channels) <= set(self.telegram_channels):
            raise ValueError("public Telegram channels must be listed as references")
        object.__setattr__(self, "telegram_public_channels", public_channels)
        realtime_channels = _clean(self.telegram_realtime_channels)
        if not set(realtime_channels) <= set(self.telegram_channels):
            raise ValueError("realtime Telegram channels must be listed as references")
        object.__setattr__(self, "telegram_realtime_channels", realtime_channels)
        object.__setattr__(self, "evidence_urls", evidence_urls)
        object.__setattr__(self, "risk_notes", _clean(self.risk_notes))
        object.__setattr__(self, "aliases", _clean(self.aliases))

    @property
    def can_establish_origin(self) -> bool:
        return ActorCapability.ESTABLISH_ORIGIN in self.capabilities

    @property
    def can_bind_token(self) -> bool:
        return ActorCapability.BIND_CA in self.capabilities

    @property
    def can_create_catalyst(self) -> bool:
        return ActorCapability.CREATE_CATALYST in self.capabilities

    @property
    def can_counter_authoritatively(self) -> bool:
        return ActorCapability.AUTHORITATIVE_COUNTER in self.capabilities

    @property
    def can_propagate(self) -> bool:
        return ActorCapability.PROPAGATE in self.capabilities

    @property
    def is_propagation_only(self) -> bool:
        return set(self.capabilities) <= {ActorCapability.PROPAGATE}

    def to_payload(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "handle": self.handle,
            "tier": self.tier.value,
            "tier_basis": self.tier_basis,
            "ecosystems": list(self.ecosystems),
            "capabilities": [item.value for item in self.capabilities],
            "display_name": self.display_name,
            "role": self.role,
            "languages": list(self.languages),
            "regions": list(self.regions),
            "telegram_channels": list(self.telegram_channels),
            "evidence_urls": list(self.evidence_urls),
            "priority": self.priority,
            "risk_notes": list(self.risk_notes),
            "aliases": list(self.aliases),
            "monitor_x": self.monitor_x,
            "monitor_reposts": self.monitor_reposts,
            "telegram_public_channels": list(self.telegram_public_channels),
            "telegram_realtime_channels": list(self.telegram_realtime_channels),
        }


def _clean(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)
