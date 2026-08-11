"""Runtime-owned actor identities; model output cannot assign authority tiers."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import urlsplit
import re

from .actor_catalog import DEFAULT_ACTOR_CATALOG
from .actors import ActorCapability, ActorRef, ActorTier


_AUTHOR_ID = re.compile(r"[1-9][0-9]{5,24}")


def _x_prefixes(handle: str) -> tuple[str, ...]:
    return (
        f"https://x.com/{handle}/status/",
        f"https://twitter.com/{handle}/status/",
    )


@dataclass(frozen=True, slots=True)
class ActorRegistration:
    actor: ActorRef
    source_prefixes: tuple[str, ...]
    author_ids: tuple[str, ...]
    aliases: tuple[str, ...] = ()
    narrative_keys: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        prefixes = tuple(dict.fromkeys(item.strip() for item in self.source_prefixes))
        aliases = tuple(dict.fromkeys(
            item.strip().lstrip("@").casefold() for item in self.aliases if item.strip()
        ))
        keys = tuple(dict.fromkeys(
            item.strip().casefold() for item in self.narrative_keys if item.strip()
        ))
        author_ids = tuple(dict.fromkeys(item.strip() for item in self.author_ids))
        if not prefixes or any(
            urlsplit(item).scheme != "https" or not urlsplit(item).hostname
            for item in prefixes
        ):
            raise ValueError("actor registrations require bounded HTTPS source prefixes")
        if self.actor.tier is ActorTier.ORIGINAL_CREATOR and not keys:
            raise ValueError("original creators require explicit narrative scopes")
        if any(not _AUTHOR_ID.fullmatch(item) for item in author_ids):
            raise ValueError("registered author IDs must be stable numeric identities")
        object.__setattr__(self, "source_prefixes", prefixes)
        object.__setattr__(self, "author_ids", author_ids)
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "narrative_keys", keys)

    @property
    def handles(self) -> frozenset[str]:
        return frozenset((self.actor.handle.casefold(), *self.aliases))

    def permits(
        self, handle: str, author_id: str, url: str, narrative_key: str
    ) -> bool:
        key = narrative_key.strip().casefold()
        in_scope = not self.narrative_keys or key in self.narrative_keys
        return (
            handle.strip().lstrip("@").casefold() in self.handles
            and author_id in self.author_ids
            and any(url.casefold().startswith(prefix.casefold()) for prefix in self.source_prefixes)
            and in_scope
        )


class ActorRegistry:
    """Immutable trust boundary populated by reviewed configuration."""

    def __init__(self, registrations: tuple[ActorRegistration, ...]) -> None:
        by_id: dict[str, ActorRegistration] = {}
        by_handle: dict[str, ActorRegistration] = {}
        by_telegram: dict[str, ActorRegistration] = {}
        for registration in registrations:
            actor_id = registration.actor.actor_id
            if actor_id in by_id:
                raise ValueError(f"duplicate actor registration: {actor_id}")
            by_id[actor_id] = registration
            for handle in registration.handles:
                if handle in by_handle:
                    raise ValueError(f"duplicate registered handle: {handle}")
                by_handle[handle] = registration
            telegram_channels = dict.fromkeys((
                *registration.actor.telegram_public_channels,
                *registration.actor.telegram_realtime_channels,
            ))
            for channel in telegram_channels:
                key = channel.casefold()
                if key in by_telegram:
                    raise ValueError(f"duplicate monitored Telegram channel: {channel}")
                by_telegram[key] = registration
        self._by_id = MappingProxyType(by_id)
        self._by_handle = MappingProxyType(by_handle)
        self._by_telegram = MappingProxyType(by_telegram)

    def resolve(self, handle: str) -> ActorRef:
        normalized = handle.strip().lstrip("@").casefold()
        registration = self._by_handle.get(normalized)
        if registration is not None:
            return registration.actor
        return ActorRef(
            f"x:{normalized}", normalized, ActorTier.UNKNOWN, "", (),
            (ActorCapability.PROPAGATE,),
        )

    def permits(
        self,
        actor: ActorRef,
        observed_handle: str,
        observed_author_id: str,
        source_url: str,
        narrative_key: str,
    ) -> bool:
        registration = self._by_id.get(actor.actor_id)
        if registration is not None:
            return registration.actor == actor and registration.permits(
                observed_handle, observed_author_id, source_url, narrative_key
            )
        expected = self.resolve(observed_handle)
        return (
            actor == expected
            and actor.tier is ActorTier.UNKNOWN
            and any(
                source_url.casefold().startswith(prefix.casefold())
                for prefix in _x_prefixes(actor.handle)
            )
        )

    def resolve_telegram(self, channel: str) -> ActorRef | None:
        registration = self._by_telegram.get(channel.strip().lstrip("@").casefold())
        return registration.actor if registration is not None else None

    def registrations(self) -> tuple[ActorRegistration, ...]:
        return tuple(self._by_id.values())


def _registered(
    handle: str,
    tier: ActorTier,
    basis: str,
    *,
    author_ids: tuple[str, ...] = (),
    ecosystems: tuple[str, ...] = (),
    capabilities: tuple[ActorCapability, ...] = (),
    display_name: str = "",
    role: str = "",
    languages: tuple[str, ...] = (),
    regions: tuple[str, ...] = (),
    telegram_channels: tuple[str, ...] = (),
    telegram_public_channels: tuple[str, ...] = (),
    telegram_realtime_channels: tuple[str, ...] = (),
    evidence_urls: tuple[str, ...] = (),
    priority: int = 50,
    risk_notes: tuple[str, ...] = (),
    aliases: tuple[str, ...] = (),
    monitor_x: bool = True,
    monitor_reposts: bool = False,
) -> ActorRegistration:
    actor = ActorRef(
        actor_id=f"x:{handle.casefold()}",
        handle=handle,
        tier=tier,
        tier_basis=basis,
        ecosystems=ecosystems,
        capabilities=capabilities,
        display_name=display_name,
        role=role,
        languages=languages,
        regions=regions,
        telegram_channels=telegram_channels,
        evidence_urls=evidence_urls,
        priority=priority,
        risk_notes=risk_notes,
        aliases=aliases,
        monitor_x=monitor_x,
        monitor_reposts=monitor_reposts,
        telegram_public_channels=telegram_public_channels,
        telegram_realtime_channels=telegram_realtime_channels,
    )
    return ActorRegistration(actor, _x_prefixes(handle), author_ids, aliases)


DEFAULT_ACTOR_REGISTRY = ActorRegistry(tuple(
    _registered(
        item.handle, item.tier, item.basis,
        author_ids=item.author_ids,
        ecosystems=item.ecosystems,
        capabilities=item.capabilities,
        display_name=item.display_name,
        role=item.role,
        languages=item.languages,
        regions=item.regions,
        telegram_channels=item.telegram_channels,
        telegram_public_channels=item.telegram_public_channels,
        telegram_realtime_channels=item.telegram_realtime_channels,
        evidence_urls=item.evidence_urls,
        priority=item.priority,
        risk_notes=item.risk_notes,
        aliases=item.aliases,
        monitor_x=item.monitor_x,
        monitor_reposts=item.monitor_reposts,
    )
    for item in DEFAULT_ACTOR_CATALOG
))
