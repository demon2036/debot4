"""Immutable, score-free v6 live narrative gate types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math

from .domain import Readiness
from .models import aware_utc


GATE_SCHEMA = "v6.live_narrative_gate.v1"


class GateStatus(str, Enum):
    PASS = "PASS"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class GatePolicy:
    require_historical_kol_evidence: bool = True
    allow_historical_kol_participation_proxy: bool = True
    maximum_current_wave_age_seconds: float = 20.0

    def __post_init__(self) -> None:
        age = self.maximum_current_wave_age_seconds
        if not isinstance(self.require_historical_kol_evidence, bool):
            raise ValueError("require_historical_kol_evidence must be boolean")
        if not isinstance(self.allow_historical_kol_participation_proxy, bool):
            raise ValueError("allow_historical_kol_participation_proxy must be boolean")
        if isinstance(age, bool) or not isinstance(age, (int, float)):
            raise ValueError("maximum_current_wave_age_seconds must be positive")
        age = float(age)
        if not math.isfinite(age) or age <= 0:
            raise ValueError("maximum_current_wave_age_seconds must be positive")
        object.__setattr__(self, "maximum_current_wave_age_seconds", age)

    def to_payload(self) -> dict[str, object]:
        return {
            "require_historical_kol_evidence": self.require_historical_kol_evidence,
            "allow_historical_kol_participation_proxy": (
                self.allow_historical_kol_participation_proxy
            ),
            "maximum_current_wave_age_seconds": self.maximum_current_wave_age_seconds,
        }


@dataclass(frozen=True, slots=True)
class CurrentWaveInput:
    token_address: str
    group: str
    signal_identity: str
    provider_at: datetime
    available_at: datetime
    assessed_at: datetime
    qualified: bool
    security_passed: bool
    evidence_quality: str
    chain_verified: bool
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_address", self.token_address.strip().lower())
        object.__setattr__(self, "group", self.group.strip())
        object.__setattr__(self, "signal_identity", self.signal_identity.strip())
        object.__setattr__(self, "evidence_quality", self.evidence_quality.strip())
        for name in ("provider_at", "available_at", "assessed_at"):
            object.__setattr__(self, name, aware_utc(getattr(self, name), name))
        if not self.token_address or not self.group or not self.signal_identity:
            raise ValueError("current wave identity fields are required")


@dataclass(frozen=True, slots=True)
class CurrentWaveAssessment:
    status: GateStatus
    reasons: tuple[str, ...]
    group: str | None = None
    signal_identity: str | None = None
    provider_at: datetime | None = None
    available_at: datetime | None = None
    assessed_at: datetime | None = None
    age_seconds: float | None = None
    maximum_age_seconds: float | None = None
    evidence_quality: str | None = None
    chain_verified: bool | None = None

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "reasons": list(self.reasons),
            "group": self.group,
            "signal_identity": self.signal_identity,
            "provider_at": _iso(self.provider_at),
            "available_at": _iso(self.available_at),
            "assessed_at": _iso(self.assessed_at),
            "age_seconds": self.age_seconds,
            "maximum_age_seconds": self.maximum_age_seconds,
            "evidence_quality": self.evidence_quality,
            "chain_verified": self.chain_verified,
            "authorizes_current_wave": self.status is GateStatus.PASS,
        }


@dataclass(frozen=True, slots=True)
class NarrativeGateDecision:
    status: GateStatus
    decided_at: datetime
    reasons: tuple[str, ...]
    narrative_readiness: Readiness
    research_status: str
    historical_kol_qualified: bool
    current_wave: CurrentWaveAssessment
    identity: str
    identity_hash: str
    dossier_hash: str
    valuation_hash: str | None
    historical_kol_qualification_kind: str | None = None

    @property
    def passed(self) -> bool:
        return self.status is GateStatus.PASS

    def to_metadata(self) -> dict[str, object]:
        return {
            "schema": GATE_SCHEMA,
            "status": self.status.value,
            "passed": self.passed,
            "decided_at": self.decided_at.isoformat(),
            "reasons": list(self.reasons),
            "narrative_readiness": self.narrative_readiness.value,
            "research_status": self.research_status,
            "historical_kol_qualified": self.historical_kol_qualified,
            "historical_kol_qualification_kind": self.historical_kol_qualification_kind,
            "current_wave": self.current_wave.to_payload(),
            "identity": self.identity,
            "identity_hash": self.identity_hash,
            "dossier_hash": self.dossier_hash,
            "valuation_hash": self.valuation_hash,
        }


def _iso(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()
