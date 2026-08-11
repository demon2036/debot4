"""Explicit, score-free output of a unified narrative investigation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .actors import ActorTier
from .domain import ConsensusStage, TokenRef
from .investigation_domain import (
    CarrierBinding,
    DiscoveryMode,
    NarrativeVerdict,
    PumpPhase,
)


def _token_payload(token: TokenRef | None) -> dict[str, str] | None:
    if token is None:
        return None
    return {"chain": token.chain, "address": token.address}


@dataclass(frozen=True, slots=True)
class CarrierFinding:
    token: TokenRef
    symbol: str
    binding: CarrierBinding
    role: str
    evidence_ids: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "token": _token_payload(self.token),
            "symbol": self.symbol,
            "binding": self.binding.value,
            "role": self.role,
            "evidence_ids": list(self.evidence_ids),
        }


@dataclass(frozen=True, slots=True)
class InvestigationReport:
    identity: str
    identity_hash: str
    mode: DiscoveryMode
    trigger_id: str
    narrative_key: str
    as_of: datetime
    source_event_id: str | None
    source_actor_handle: str | None
    source_actor_tier: ActorTier | None
    propagation_reason: str | None
    current_catalyst_id: str | None
    carrier_binding: CarrierBinding
    narrative_leader: TokenRef | None
    market_leader: TokenRef | None
    carriers: tuple[CarrierFinding, ...]
    historical_kol_confirmed: bool
    current_debot_confirmed: bool
    stage: ConsensusStage
    pump_phase: PumpPhase
    verdict: NarrativeVerdict
    reasons: tuple[str, ...]
    unknowns: tuple[str, ...]
    counterevidence_ids: tuple[str, ...]
    invalidation_conditions: tuple[str, ...]
    timeline: tuple[str, ...]

    def to_payload(self, *, include_identity: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "mode": self.mode.value,
            "trigger_id": self.trigger_id,
            "narrative_key": self.narrative_key,
            "as_of": self.as_of.isoformat(),
            "source_event": self.source_event_id,
            "source_actor": {
                "handle": self.source_actor_handle,
                "tier": None if self.source_actor_tier is None else self.source_actor_tier.value,
            },
            "propagation_reason": self.propagation_reason,
            "current_catalyst": self.current_catalyst_id,
            "carrier_binding": self.carrier_binding.value,
            "narrative_leader": _token_payload(self.narrative_leader),
            "market_leader": _token_payload(self.market_leader),
            "carriers": [item.to_payload() for item in self.carriers],
            "historical_kol_confirmed": self.historical_kol_confirmed,
            "current_debot_confirmed": self.current_debot_confirmed,
            "stage": self.stage.value,
            "pump_phase": self.pump_phase.value,
            "verdict": self.verdict.value,
            "reasons": list(self.reasons),
            "unknowns": list(self.unknowns),
            "counterevidence_ids": list(self.counterevidence_ids),
            "invalidation_conditions": list(self.invalidation_conditions),
            "timeline": list(self.timeline),
        }
        if include_identity:
            payload.update({"identity": self.identity, "identity_hash": self.identity_hash})
        return payload
