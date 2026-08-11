"""Immutable point-in-time inputs for a narrative investigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from urllib.parse import urlsplit

from .actors import ActorRef
from .domain import TokenRef
from .investigation_domain import (
    CarrierBinding,
    DiscoveryMode,
    EndorsementScope,
    NarrativeAction,
    NarrativeEventKind,
    PumpPhase,
)
from .models import CurrentSignalBoundary, aware_utc
from .source_receipts import VerifiedSourceReceipt, verify_source_receipt


_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")


@dataclass(frozen=True, slots=True)
class NarrativeEvent:
    event_id: str
    kind: NarrativeEventKind
    actor: ActorRef
    action: NarrativeAction
    endorsement: EndorsementScope
    receipt: VerifiedSourceReceipt
    claim: str
    first_seen_at: datetime
    token_address: str = ""
    exact_ca: bool = False
    parent_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        event_id = self.event_id.strip()
        claim = self.claim.strip()
        token = self.token_address.strip().lower()
        kind = NarrativeEventKind(self.kind)
        first_seen = aware_utc(self.first_seen_at, "first_seen_at")
        if not event_id or not claim:
            raise ValueError("event identity and claim are required")
        if not verify_source_receipt(self.receipt):
            raise ValueError("a sealed verified source receipt is required")
        if first_seen < self.receipt.published_at:
            raise ValueError("first_seen_at cannot predate published_at")
        if self.receipt.fetched_at < first_seen:
            raise ValueError("captured_at cannot predate first_seen_at")
        if token and not _ADDRESS.fullmatch(token):
            raise ValueError("event token_address must be an exact BSC address")
        if self.exact_ca and not token:
            raise ValueError("exact_ca evidence requires a token address")
        if kind is NarrativeEventKind.TOKEN_BINDING and not self.exact_ca:
            raise ValueError("token binding events require exact_ca evidence")
        parents = tuple(dict.fromkeys(item.strip() for item in self.parent_ids if item.strip()))
        if event_id in parents:
            raise ValueError("an event cannot be its own parent")
        object.__setattr__(self, "event_id", event_id)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "action", NarrativeAction(self.action))
        object.__setattr__(self, "endorsement", EndorsementScope(self.endorsement))
        object.__setattr__(self, "first_seen_at", first_seen)
        object.__setattr__(self, "claim", claim)
        object.__setattr__(self, "token_address", token)
        object.__setattr__(self, "parent_ids", parents)

    def usable_at(self, cutoff: datetime) -> bool:
        as_of = aware_utc(cutoff, "cutoff")
        return self.published_at <= as_of and self.captured_at <= as_of

    @property
    def published_at(self) -> datetime:
        return self.receipt.published_at

    @property
    def captured_at(self) -> datetime:
        return self.receipt.fetched_at

    @property
    def source_url(self) -> str:
        return self.receipt.canonical_url

    @property
    def independence_group(self) -> str:
        return f"source-author:{self.receipt.author_id}"


@dataclass(frozen=True, slots=True)
class CarrierCandidate:
    token: TokenRef
    symbol: str
    name: str
    binding: CarrierBinding
    binding_event_ids: tuple[str, ...]
    created_at: datetime
    first_seen_at: datetime
    market_cap_usd: float | None = None
    market_as_of: datetime | None = None

    def __post_init__(self) -> None:
        symbol = self.symbol.strip()
        name = self.name.strip()
        binding = CarrierBinding(self.binding)
        created = aware_utc(self.created_at, "created_at")
        seen = aware_utc(self.first_seen_at, "first_seen_at")
        event_ids = tuple(dict.fromkeys(
            item.strip() for item in self.binding_event_ids if item.strip()
        ))
        if not symbol or not name or seen < created:
            raise ValueError("carrier identity and chronological discovery are required")
        if binding not in {CarrierBinding.UNVERIFIED} and not event_ids:
            raise ValueError("a classified carrier binding requires evidence")
        cap = self.market_cap_usd
        if cap is not None:
            if isinstance(cap, bool) or not isinstance(cap, (int, float)):
                raise ValueError("market_cap_usd must be positive")
            if not math.isfinite(float(cap)) or cap <= 0 or self.market_as_of is None:
                raise ValueError("market_cap_usd requires a valid market timestamp")
            object.__setattr__(self, "market_cap_usd", float(cap))
            object.__setattr__(self, "market_as_of", aware_utc(self.market_as_of, "market_as_of"))
        elif self.market_as_of is not None:
            raise ValueError("market_as_of requires market_cap_usd")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "binding", binding)
        object.__setattr__(self, "binding_event_ids", event_ids)
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "first_seen_at", seen)


@dataclass(frozen=True, slots=True)
class CapitalContext:
    historical_kol: tuple[CurrentSignalBoundary, ...] = ()
    current_debot: CurrentSignalBoundary | None = None
    current_debot_qualified: bool = False


@dataclass(frozen=True, slots=True)
class InvestigationRequest:
    mode: DiscoveryMode
    trigger_id: str
    narrative_key: str
    as_of: datetime
    events: tuple[NarrativeEvent, ...]
    carriers: tuple[CarrierCandidate, ...]
    capital: CapitalContext = CapitalContext()
    trigger_event_id: str | None = None
    trigger_token: TokenRef | None = None
    pump_phase: PumpPhase = PumpPhase.UNKNOWN
    invalidation_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        mode = DiscoveryMode(self.mode)
        cutoff = aware_utc(self.as_of, "as_of")
        trigger_id = self.trigger_id.strip()
        narrative = self.narrative_key.strip()
        event_ids = [item.event_id for item in self.events]
        addresses = [item.token.address for item in self.carriers]
        if not trigger_id or not narrative:
            raise ValueError("trigger_id and narrative_key are required")
        if len(set(event_ids)) != len(event_ids) or len(set(addresses)) != len(addresses):
            raise ValueError("event and carrier identities must be unique")
        if mode is DiscoveryMode.ACTIVE_ACTOR and self.trigger_event_id not in event_ids:
            raise ValueError("active discovery requires its exact trigger event")
        if mode is DiscoveryMode.PASSIVE_DEBOT and self.trigger_token is None:
            raise ValueError("passive discovery requires the DeBot trigger token")
        if mode is DiscoveryMode.PASSIVE_DEBOT and self.capital.current_debot is None:
            raise ValueError("passive discovery requires the current DeBot boundary")
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "as_of", cutoff)
        object.__setattr__(self, "trigger_id", trigger_id)
        object.__setattr__(self, "narrative_key", narrative)
        object.__setattr__(self, "pump_phase", PumpPhase(self.pump_phase))
