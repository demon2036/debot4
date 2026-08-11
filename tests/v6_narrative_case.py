from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json

from debot4.v6.narrative import (
    ActorCapability,
    ActorRef,
    ActorRegistration,
    ActorRegistry,
    ActorTier,
    CapitalContext,
    CarrierBinding,
    CarrierCandidate,
    CurrentSignalBoundary,
    EndorsementScope,
    EvidenceProvider,
    NarrativeAction,
    NarrativeEvent,
    NarrativeEventKind,
    TokenRef,
)
from debot4.v6.narrative.source_receipts import _TRUSTED_RECEIPT_ISSUER
from debot4.v6.narrative.event_semantics import derive_event_semantics


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = TokenRef("bsc", "0x1111111111111111111111111111111111111111")
OTHER = TokenRef("bsc", "0x2222222222222222222222222222222222222222")


def _actor(
    handle: str,
    actor_id: str,
    tier: ActorTier,
    capabilities: tuple[ActorCapability, ...],
) -> ActorRegistration:
    actor = ActorRef(actor_id, handle, tier, "test-reviewed identity", ("bsc",), capabilities)
    suffix = actor_id.rsplit(":", 1)[-1]
    numeric = str(100_000 + sum(ord(char) for char in suffix))
    return ActorRegistration(
        actor,
        (f"https://x.com/{handle}/status/",),
        (numeric,),
    )


REGISTRY = ActorRegistry((
    _actor(
        "originator", "x:originator", ActorTier.GLOBAL_AGENDA,
        (ActorCapability.ESTABLISH_ORIGIN, ActorCapability.CREATE_CATALYST),
    ),
    _actor(
        "official", "x:official", ActorTier.ECOSYSTEM_AUTHORITY,
        (
            ActorCapability.ESTABLISH_ORIGIN,
            ActorCapability.CREATE_CATALYST,
            ActorCapability.BIND_CA,
            ActorCapability.AUTHORITATIVE_COUNTER,
        ),
    ),
    _actor(
        "expert", "x:expert", ActorTier.DOMAIN_EXPERT,
        (ActorCapability.CREATE_CATALYST, ActorCapability.PROPAGATE),
    ),
    _actor(
        "kol", "x:kol", ActorTier.PROPAGATION_KOL,
        (ActorCapability.PROPAGATE,),
    ),
))


def _numeric(handle: str) -> str:
    registration = next(
        (item for item in REGISTRY.registrations() if item.actor.handle == handle), None
    )
    if registration is not None:
        return registration.author_ids[0]
    return str(200_000 + sum(ord(char) for char in handle))


def event(
    source_label: str,
    kind: NarrativeEventKind,
    handle: str,
    minutes: int,
    *,
    parents: tuple[str, ...] = (),
    token: TokenRef | None = None,
) -> NarrativeEvent:
    published = NOW + timedelta(minutes=minutes)
    fetched = published + timedelta(seconds=1)
    address = "" if token is None else token.address
    if kind is NarrativeEventKind.COUNTER_EVIDENCE:
        content = f"example-narrative is a fake token, not associated {address}"
    elif kind is NarrativeEventKind.TOKEN_BINDING:
        content = f"official example-narrative launch exact CA {address}"
    elif kind is NarrativeEventKind.SOURCE_EVENT:
        content = "introducing example-narrative, this is great"
    else:
        content = "great report about example-narrative"
    raw = json.dumps({
        "id": source_label, "author": handle, "text": content,
    }, sort_keys=True).encode()
    status_id = str(1_000_000_000_000_000_000 + int(
        sha256(source_label.encode()).hexdigest()[:12], 16
    ))
    receipt = _TRUSTED_RECEIPT_ISSUER.x_status(
        provider=EvidenceProvider.X_GRAPHQL,
        status_id=status_id,
        author_id=_numeric(handle),
        author_handle=handle,
        content=content,
        published_at=published,
        fetched_at=fetched,
        raw_payload=raw,
        response_identity=f"test-response:{sha256(raw).hexdigest()}",
    )
    actor = REGISTRY.resolve(handle)
    derived = next(
        item for item in derive_event_semantics(actor, receipt, "example-narrative")
        if item.kind is kind
    )
    return NarrativeEvent(
        derived.event_id, derived.kind, actor, derived.action, derived.endorsement,
        receipt, derived.claim, fetched, derived.token_address, derived.exact_ca,
        parents,
    )


@dataclass(frozen=True)
class CompleteCase:
    events: tuple[NarrativeEvent, ...]
    carriers: tuple[CarrierCandidate, ...]
    capital: CapitalContext
    source_id: str
    binding_id: str
    catalyst_id: str
    propagation_ids: tuple[str, ...]


def complete_case() -> CompleteCase:
    source = event("source", NarrativeEventKind.SOURCE_EVENT, "originator", -120)
    binding = event(
        "binding", NarrativeEventKind.TOKEN_BINDING, "official", -90,
        parents=(source.event_id,), token=TOKEN,
    )
    catalyst = event(
        "catalyst", NarrativeEventKind.CURRENT_CATALYST, "expert", -20,
        parents=(source.event_id,),
    )
    spread_a = event(
        "spread-a", NarrativeEventKind.PROPAGATION, "reporter_a", -10,
        parents=(catalyst.event_id,),
    )
    spread_b = event(
        "spread-b", NarrativeEventKind.PROPAGATION, "reporter_b", -8,
        parents=(catalyst.event_id,),
    )
    events = (source, binding, catalyst, spread_a, spread_b)
    carrier = CarrierCandidate(
        TOKEN, "MEME", "Narrative Meme", CarrierBinding.OFFICIAL_EXACT_CA,
        (binding.event_id,), NOW - timedelta(minutes=100), NOW - timedelta(minutes=99),
        500_000, NOW - timedelta(seconds=1),
    )
    current = CurrentSignalBoundary(
        "current", NOW - timedelta(minutes=5), NOW - timedelta(minutes=4, seconds=59)
    )
    prior = CurrentSignalBoundary(
        "prior", NOW - timedelta(days=1), NOW - timedelta(days=1) + timedelta(seconds=1)
    )
    return CompleteCase(
        events,
        (carrier,),
        CapitalContext((prior,), current, True),
        source.event_id,
        binding.event_id,
        catalyst.event_id,
        (spread_a.event_id, spread_b.event_id),
    )
