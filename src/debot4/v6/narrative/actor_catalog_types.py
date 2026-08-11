"""Validated metadata for reviewed X monitoring targets."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlsplit

from .actors import ActorCapability, ActorTier


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_AUTHOR_ID = re.compile(r"[1-9][0-9]{5,24}")

AGENDA = (
    ActorCapability.ESTABLISH_ORIGIN,
    ActorCapability.CREATE_CATALYST,
    ActorCapability.AUTHORITATIVE_COUNTER,
    ActorCapability.PROPAGATE,
)
CATALYST = (ActorCapability.CREATE_CATALYST, ActorCapability.PROPAGATE)
KOL = (ActorCapability.PROPAGATE,)
PROFILE_REVIEW = "FxTwitter stable ID and public profile reviewed 2026-08-10"
EXACT_POST_REVIEW = (
    "FxTwitter stable ID, public profile, and exact authored status reviewed 2026-08-10"
)


@dataclass(frozen=True, slots=True)
class CatalogActor:
    handle: str
    display_name: str
    role: str
    tier: ActorTier
    basis: str
    author_ids: tuple[str, ...]
    ecosystems: tuple[str, ...]
    capabilities: tuple[ActorCapability, ...]
    languages: tuple[str, ...] = ("en",)
    regions: tuple[str, ...] = ("global",)
    telegram_channels: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    priority: int = 50
    risk_notes: tuple[str, ...] = ()
    evidence_urls: tuple[str, ...] = ()
    monitor_x: bool = True
    monitor_reposts: bool = False
    telegram_public_channels: tuple[str, ...] = ()
    telegram_realtime_channels: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@")
        ids = _unique(self.author_ids)
        evidence = _unique(self.evidence_urls or (f"https://x.com/{handle}",))
        if not _HANDLE.fullmatch(handle) or not ids:
            raise ValueError("catalog actors require a valid handle and stable ID")
        if any(not _AUTHOR_ID.fullmatch(item) for item in ids):
            raise ValueError("catalog actor IDs must be stable numeric identities")
        if not self.display_name.strip() or not self.role.strip() or not self.basis.strip():
            raise ValueError("catalog actor identity and role evidence are required")
        if not 1 <= self.priority <= 100:
            raise ValueError("catalog actor priority must be between 1 and 100")
        if any(not _https_url(item) for item in evidence):
            raise ValueError("catalog evidence URLs must use HTTPS")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "author_ids", ids)
        object.__setattr__(self, "evidence_urls", evidence)
        for field_name in (
            "ecosystems", "languages", "regions", "telegram_channels",
            "aliases", "risk_notes", "telegram_public_channels",
            "telegram_realtime_channels",
        ):
            object.__setattr__(self, field_name, _unique(getattr(self, field_name)))
        if not set(self.telegram_public_channels) <= set(self.telegram_channels):
            raise ValueError("public Telegram channels must be listed as references")
        if not set(self.telegram_realtime_channels) <= set(self.telegram_channels):
            raise ValueError("realtime Telegram channels must be listed as references")


def actor(
    handle: str,
    author_id: str,
    display_name: str,
    role: str,
    tier: ActorTier,
    ecosystems: tuple[str, ...],
    capabilities: tuple[ActorCapability, ...],
    *,
    languages: tuple[str, ...] = ("en",),
    regions: tuple[str, ...] = ("global",),
    telegram: tuple[str, ...] = (),
    telegram_public: tuple[str, ...] = (),
    telegram_realtime: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    priority: int = 50,
    risks: tuple[str, ...] = (),
    monitor_x: bool = True,
    monitor_reposts: bool = False,
    basis: str = PROFILE_REVIEW,
    evidence: tuple[str, ...] = (),
) -> CatalogActor:
    realtime_refs = _unique((*telegram_public, *telegram_realtime))
    telegram_refs = _unique((*telegram, *telegram_public, *realtime_refs))
    return CatalogActor(
        handle=handle,
        display_name=display_name,
        role=role,
        tier=tier,
        basis=basis,
        author_ids=(author_id,),
        ecosystems=ecosystems,
        capabilities=capabilities,
        languages=languages,
        regions=regions,
        telegram_channels=telegram_refs,
        aliases=aliases,
        priority=priority,
        risk_notes=risks,
        evidence_urls=_unique((f"https://x.com/{handle}", *evidence)),
        monitor_x=monitor_x,
        monitor_reposts=monitor_reposts,
        telegram_public_channels=_unique(telegram_public),
        telegram_realtime_channels=realtime_refs,
    )


def _unique(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(item.strip() for item in values if item.strip()))


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)
