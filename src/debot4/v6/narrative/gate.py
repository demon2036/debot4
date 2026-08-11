"""Pure fail-closed v6 narrative, history, and current-wave gate."""

from __future__ import annotations

from datetime import datetime

from .domain import Readiness
from .dossier import NarrativeDossier
from .readiness import ReadinessPolicy, evaluate_readiness
from .valuation import ValuationView
from .current_wave import assess_current_wave
from .gate_models import (
    GATE_SCHEMA,
    CurrentWaveInput,
    GatePolicy,
    GateStatus,
    NarrativeGateDecision,
)
from .hashing import canonical_sha256, dossier_hash, valuation_payload
from .models import aware_utc, is_exact_bsc_token
from .results import NarrativeResearchResult, ResearchStatus


def evaluate_narrative_gate(
    dossier: NarrativeDossier,
    valuation: ValuationView | None,
    research: NarrativeResearchResult,
    current_wave: CurrentWaveInput | None,
    *,
    decided_at: datetime,
    policy: GatePolicy = GatePolicy(),
) -> NarrativeGateDecision:
    cutoff = aware_utc(decided_at, "decided_at")
    narrative = evaluate_readiness(
        dossier,
        valuation=valuation,
        policy=ReadinessPolicy(require_capital_confirmation=False),
    )
    current = assess_current_wave(
        current_wave,
        token=dossier.token,
        decided_at=cutoff,
        maximum_age_seconds=policy.maximum_current_wave_age_seconds,
    )
    digest = dossier_hash(dossier)
    valuation_data = valuation_payload(valuation)
    valuation_digest = None if valuation_data is None else canonical_sha256(valuation_data)
    rejects = _integrity_reasons(
        dossier, valuation, research, current_wave, digest, cutoff
    )
    if research.status is ResearchStatus.REJECT:
        rejects.extend(f"research:{item}" for item in research.reasons)
    if narrative.status is Readiness.REJECT:
        rejects.extend(f"narrative:{item}" for item in narrative.reasons)
    if current.status is GateStatus.REJECT:
        rejects.extend(current.reasons)
    waits: list[str] = []
    if research.status is ResearchStatus.WAIT:
        waits.extend(f"research:{item}" for item in research.reasons)
    if narrative.status is not Readiness.PASS_TO_EXECUTION:
        waits.extend(f"narrative:{item}" for item in narrative.reasons)
    if policy.require_historical_kol_evidence and not research.historical_kol.qualified:
        waits.append("historical_kol_evidence_missing")
    if (
        research.historical_kol.qualification_kind == "rank_kol_count_increase_proxy"
        and not policy.allow_historical_kol_participation_proxy
    ):
        waits.append("historical_kol_wallet_buy_missing")
    if current.status is GateStatus.WAIT:
        waits.extend(current.reasons)
    reasons = tuple(dict.fromkeys(rejects or waits or ["v6_narrative_gate_passed"]))
    status = GateStatus.REJECT if rejects else GateStatus.WAIT if waits else GateStatus.PASS
    material = {
        "schema": GATE_SCHEMA,
        "decided_at": cutoff.isoformat(),
        "policy": policy.to_payload(),
        "dossier_hash": digest,
        "valuation_hash": valuation_digest,
        "research_identity": research.identity,
        "research_hash": research.identity_hash,
        "current_wave": current.to_payload(),
        "status": status.value,
        "reasons": list(reasons),
    }
    identity_hash = canonical_sha256(material)
    return NarrativeGateDecision(
        status=status,
        decided_at=cutoff,
        reasons=reasons,
        narrative_readiness=narrative.status,
        research_status=research.status.value,
        historical_kol_qualified=research.historical_kol.qualified,
        current_wave=current,
        identity=f"{GATE_SCHEMA}:{identity_hash}",
        identity_hash=identity_hash,
        dossier_hash=digest,
        valuation_hash=valuation_digest,
        historical_kol_qualification_kind=research.historical_kol.qualification_kind,
    )


def _integrity_reasons(
    dossier: NarrativeDossier,
    valuation: ValuationView | None,
    research: NarrativeResearchResult,
    current_wave: CurrentWaveInput | None,
    digest: str,
    cutoff: datetime,
) -> list[str]:
    reasons: list[str] = []
    if not is_exact_bsc_token(dossier.token):
        reasons.append("unsupported_narrative_token")
    if dossier.as_of > cutoff:
        reasons.append("dossier_from_future")
    if valuation is not None and valuation.as_of > cutoff:
        reasons.append("valuation_from_future")
    if research.source_research.token != dossier.token:
        reasons.append("research_token_mismatch")
    if research.decision_time > cutoff:
        reasons.append("research_from_future")
    if research.decision_time != dossier.as_of:
        reasons.append("research_dossier_cutoff_mismatch")
    if research.dossier_hash != digest:
        reasons.append("research_dossier_hash_mismatch")
    if not research.identity_valid:
        reasons.append("research_identity_invalid")
    boundary = research.current_signal
    if boundary is None:
        reasons.append("research_current_signal_boundary_missing")
    elif current_wave is not None:
        if current_wave.signal_identity != boundary.signal_id:
            reasons.append("current_wave_replaced_research_signal")
        if (
            current_wave.provider_at != boundary.event_at
            or current_wave.available_at != boundary.available_at
        ):
            reasons.append("current_wave_research_boundary_mismatch")
    return reasons
