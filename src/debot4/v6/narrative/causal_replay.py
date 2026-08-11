"""Minimal point-in-time policy for narrative causal replays."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Mapping


class ReplayVerdict(str, Enum):
    CAUSAL_READY = "CAUSAL_READY"
    WAIT = "WAIT"
    REJECT = "REJECT"


class ActorRole(str, Enum):
    PRIMARY = "primary"
    AUTHORITY = "authority"
    PUBLIC_SOURCE = "public_source"
    KOL = "kol"
    WALLET = "wallet"


class ClaimRole(str, Enum):
    ORIGIN = "origin"
    CA_BINDING = "ca_binding"
    CATALYST = "catalyst"
    PROPAGATION = "propagation"
    DENIAL = "denial"


class ReplayScope(str, Enum):
    LIVE = "live"
    POSTMORTEM = "postmortem"


@dataclass(frozen=True, slots=True)
class ReplayEvidence:
    evidence_id: str
    actor: ActorRole
    claim: ClaimRole
    published_at: datetime
    known_at: datetime | None
    token_address: str = ""
    exact_ca: bool = False
    public: bool = True
    scope: ReplayScope = ReplayScope.LIVE

    def __post_init__(self) -> None:
        object.__setattr__(self, "actor", ActorRole(self.actor))
        object.__setattr__(self, "claim", ClaimRole(self.claim))
        object.__setattr__(self, "scope", ReplayScope(self.scope))
        object.__setattr__(self, "published_at", _aware(self.published_at))
        if self.known_at is not None:
            known = _aware(self.known_at)
            if known < self.published_at:
                raise ValueError("known_at cannot predate published_at")
            object.__setattr__(self, "known_at", known)
        if not self.evidence_id.strip():
            raise ValueError("evidence_id is required")


@dataclass(frozen=True, slots=True)
class CausalReplayCase:
    case_id: str
    target_address: str
    trigger_at: datetime
    buy_at: datetime
    evidence: tuple[ReplayEvidence, ...]

    def __post_init__(self) -> None:
        trigger = _aware(self.trigger_at)
        buy = _aware(self.buy_at)
        if buy < trigger:
            raise ValueError("buy_at cannot predate trigger_at")
        if not self.case_id.strip() or not self.target_address.strip():
            raise ValueError("case_id and target_address are required")
        if len({item.evidence_id for item in self.evidence}) != len(self.evidence):
            raise ValueError("evidence ids must be unique")
        object.__setattr__(self, "trigger_at", trigger)
        object.__setattr__(self, "buy_at", buy)


@dataclass(frozen=True, slots=True)
class ReplayDecision:
    verdict: ReplayVerdict
    reasons: tuple[str, ...]
    causal_evidence_ids: tuple[str, ...]
    counter_evidence_ids: tuple[str, ...]
    effective_claims: tuple[tuple[str, ClaimRole], ...]


def evaluate_causal_replay(case: CausalReplayCase) -> ReplayDecision:
    reasons: list[str] = []
    usable: list[tuple[ReplayEvidence, ClaimRole]] = []
    counters: list[str] = []
    rejects: list[str] = []
    cutoff = min(case.trigger_at, case.buy_at)
    target = _address(case.target_address)
    for item in case.evidence:
        if item.scope is ReplayScope.POSTMORTEM:
            reasons.append("postmortem_evidence_not_causal")
            continue
        if item.known_at is None:
            reasons.append("evidence_availability_unknown")
            continue
        if max(item.published_at, item.known_at) >= cutoff:
            reasons.append("evidence_not_prior_to_trigger_and_buy")
            continue
        role = effective_claim(item)
        if role is not item.claim:
            reasons.append("kol_wallet_propagation_only")
        if role is ClaimRole.DENIAL:
            counters.append(item.evidence_id)
            if item.actor in {ActorRole.PRIMARY, ActorRole.AUTHORITY} and (
                not item.token_address or _address(item.token_address) == target
            ):
                rejects.append("authoritative_denial")
            continue
        usable.append((item, role))
    if rejects:
        return _decision(ReplayVerdict.REJECT, rejects + reasons, usable, counters)
    origin = any(
        role is ClaimRole.ORIGIN
        and item.actor in {ActorRole.PRIMARY, ActorRole.AUTHORITY, ActorRole.PUBLIC_SOURCE}
        for item, role in usable
    )
    binding = any(
        role is ClaimRole.CA_BINDING
        and item.actor in {ActorRole.PRIMARY, ActorRole.AUTHORITY}
        and item.exact_ca
        and _address(item.token_address) == target
        for item, role in usable
    )
    catalyst = any(
        role is ClaimRole.CATALYST
        and item.public
        and item.actor not in {ActorRole.KOL, ActorRole.WALLET}
        for item, role in usable
    )
    if not origin:
        reasons.append("source_event_missing_at_trigger")
    if not binding:
        reasons.append("exact_ca_binding_missing")
    if not catalyst:
        reasons.append("public_catalyst_missing")
    verdict = ReplayVerdict.WAIT if reasons else ReplayVerdict.CAUSAL_READY
    return _decision(verdict, reasons or ["causal_narrative_ready"], usable, counters)


def effective_claim(item: ReplayEvidence) -> ClaimRole:
    if item.claim is ClaimRole.DENIAL:
        return ClaimRole.DENIAL
    if item.actor in {ActorRole.KOL, ActorRole.WALLET}:
        return ClaimRole.PROPAGATION
    return item.claim


def case_from_mapping(data: Mapping[str, object]) -> CausalReplayCase:
    evidence = tuple(_evidence_from_mapping(item) for item in data["evidence"])
    return CausalReplayCase(
        str(data["case_id"]), str(data["target_address"]),
        _time(data["trigger_at"]), _time(data["buy_at"]), evidence,
    )


def _evidence_from_mapping(data: Mapping[str, object]) -> ReplayEvidence:
    known = data.get("known_at")
    return ReplayEvidence(
        evidence_id=str(data["evidence_id"]),
        actor=ActorRole(str(data["actor"])),
        claim=ClaimRole(str(data["claim"])),
        published_at=_time(data["published_at"]),
        known_at=None if known is None else _time(known),
        token_address=str(data.get("token_address", "")),
        exact_ca=bool(data.get("exact_ca", False)),
        public=bool(data.get("public", True)),
        scope=ReplayScope(str(data.get("scope", "live"))),
    )


def _decision(verdict, reasons, usable, counters) -> ReplayDecision:
    claims = tuple((item.evidence_id, role) for item, role in usable)
    return ReplayDecision(
        verdict, tuple(dict.fromkeys(reasons)),
        tuple(item.evidence_id for item, _ in usable), tuple(counters), claims,
    )


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("causal replay timestamps must be timezone-aware")
    return value


def _time(value: object) -> datetime:
    return _aware(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _address(value: str) -> str:
    address = value.strip()
    return address.lower() if address.startswith("0x") else address
