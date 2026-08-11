from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from debot4.v6.narrative import (
    Canonicality,
    ComparableAnchor,
    ConsensusStage,
    Dimension,
    DimensionFinding,
    EvidenceItem,
    EvidenceRole,
    EvidenceScope,
    EvidenceSource,
    FindingState,
    NarrativeDossier,
    TokenRef,
    ValuationScenario,
    ValuationStatus,
    ValuationView,
    CurrentSignalBoundary,
    CurrentWaveInput,
    GateStatus,
    FxTwitterTweet,
    ResearchOutcome,
    ResearchStatus,
    StatusResearch,
    bind_research_to_dossier,
    evaluate_narrative_gate,
)
from debot4.v6.narrative.results import (
    BindingAssessment,
    HistoricalKolAssessment,
    NarrativeResearchResult,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = TokenRef("bsc", "0x1111111111111111111111111111111111111111")
OTHER = "0x2222222222222222222222222222222222222222"
STATUS_ID = "1234567890"


def _evidence(
    evidence_id: str,
    role: EvidenceRole,
    source: EvidenceSource = EvidenceSource.COMMUNITY,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id, source, role, evidence_id,
        NOW - timedelta(minutes=5), NOW - timedelta(minutes=4),
        NOW - timedelta(minutes=3), TOKEN.address, "actor", evidence_id,
        role is EvidenceRole.TOKEN_BINDING, f"group:{evidence_id}",
        EvidenceScope.LIVE_ELIGIBLE,
    )


def _dossier() -> NarrativeDossier:
    binding = _evidence("binding", EvidenceRole.TOKEN_BINDING, EvidenceSource.PRIMARY_ACTOR)
    items = {
        Dimension.PROPAGATION: _evidence("propagation", EvidenceRole.PROPAGATION),
        Dimension.CULTURAL_FIT: _evidence("culture", EvidenceRole.CULTURAL_CONTEXT),
        Dimension.CATALYSTS: _evidence("catalyst", EvidenceRole.CATALYST),
        Dimension.LEADER_COMPETITION: _evidence("leader", EvidenceRole.LEADER_COMPETITION),
        Dimension.CONSENSUS_STAGE: _evidence("consensus", EvidenceRole.PROPAGATION),
    }
    findings = [
        DimensionFinding(Dimension.ORIGIN, FindingState.CONFIRMED, "origin", ("binding",)),
        DimensionFinding(Dimension.LEGITIMACY, FindingState.CONFIRMED, "binding", ("binding",)),
    ]
    for dimension, item in items.items():
        state = FindingState.CONFIRMED if dimension is Dimension.LEADER_COMPETITION else FindingState.SUPPORTED
        findings.append(DimensionFinding(dimension, state, item.evidence_id, (item.evidence_id,)))
    capital = _evidence("prior-kol", EvidenceRole.CAPITAL_CONFIRMATION, EvidenceSource.KOL)
    return NarrativeDossier(
        TOKEN, NOW, "complete evidence-bound narrative", Canonicality.CREATOR_CLAIMED,
        ConsensusStage.VALIDATION, (binding, capital, *items.values()), tuple(findings),
    )


def _research(dossier: NarrativeDossier) -> NarrativeResearchResult:
    tweet = FxTwitterTweet(
        STATUS_ID, "origin", "author-1", f"Official CA: {TOKEN.address}",
        NOW - timedelta(minutes=5), NOW - timedelta(minutes=3),
        f"https://x.com/origin/status/{STATUS_ID}",
    )
    source = StatusResearch(
        TOKEN, ResearchOutcome.FETCHED, "exact_status_fetched", "lead:1",
        tweet.canonical_url, "origin", STATUS_ID, NOW - timedelta(minutes=4), tweet,
    )
    binding = next(item for item in dossier.evidence if item.evidence_id == "binding")
    history = next(item for item in dossier.evidence if item.evidence_id == "prior-kol")
    draft = NarrativeResearchResult(
        ResearchStatus.READY, ("research_prerequisites_ready",), NOW, source,
        BindingAssessment(True, "accepted", (TOKEN.address,), evidence=binding),
        HistoricalKolAssessment(True, "historical_kol_buy_qualified", (history,), ()),
        CurrentSignalBoundary("current", NOW - timedelta(seconds=10), NOW - timedelta(seconds=9)),
        "pending", "pending", "pending",
    )
    return bind_research_to_dossier(draft, dossier)


def _valuation() -> ValuationView:
    comparable = lambda address, label, cap: ComparableAnchor(
        TokenRef("bsc", address), label, cap, NOW,
        ("same narrative distribution",),
    )
    return ValuationView(
        NOW, 100_000, ValuationStatus.BOUNDED,
        (
            comparable("0x3333333333333333333333333333333333333333", "low", 300_000),
            comparable("0x4444444444444444444444444444444444444444", "high", 900_000),
        ),
        (
            ValuationScenario("base", 200_000, 400_000, "base comparable"),
            ValuationScenario("expansion", 500_000, 900_000, "strong propagation"),
        ),
    )


def _wave(**changes: object) -> CurrentWaveInput:
    values = {
        "token_address": TOKEN.address,
        "group": "SmartMoney",
        "signal_identity": "current",
        "provider_at": NOW - timedelta(seconds=10),
        "available_at": NOW - timedelta(seconds=9),
        "assessed_at": NOW - timedelta(seconds=1),
        "qualified": True,
        "security_passed": True,
        "evidence_quality": "provider_aggregate_asserted",
        "chain_verified": False,
    }
    values.update(changes)
    return CurrentWaveInput(**values)


def test_v6_gate_passes_only_complete_research_narrative_and_fresh_wave() -> None:
    dossier = _dossier()
    decision = evaluate_narrative_gate(
        dossier, _valuation(), _research(dossier), _wave(),
        decided_at=NOW + timedelta(seconds=1),
    )

    assert decision.status is GateStatus.PASS
    assert decision.passed


def test_v6_gate_waits_for_stale_wave_and_prior_kol_history() -> None:
    dossier = _dossier()
    stale = evaluate_narrative_gate(
        dossier, _valuation(), _research(dossier),
        _wave(),
        decided_at=NOW + timedelta(seconds=15),
    )
    no_history = replace(
        _research(dossier),
        historical_kol=HistoricalKolAssessment(False, "missing", (), ()),
    )
    no_history = bind_research_to_dossier(no_history, dossier)
    missing = evaluate_narrative_gate(
        dossier, _valuation(), no_history,
        _wave(group="KOL", evidence_quality="provider_ui_asserted"),
        decided_at=NOW + timedelta(seconds=1),
    )

    assert stale.status is GateStatus.WAIT
    assert "current_debot_wave_stale" in stale.reasons
    assert missing.status is GateStatus.WAIT
    assert "historical_kol_evidence_missing" in missing.reasons


def test_v6_gate_rejects_wrong_token_or_tampered_research_hash() -> None:
    dossier = _dossier()
    wrong = evaluate_narrative_gate(
        dossier, _valuation(), _research(dossier),
        _wave(token_address=OTHER, signal_identity="replacement"),
        decided_at=NOW + timedelta(seconds=1),
    )
    tampered = replace(_research(dossier), dossier_hash="0" * 64)
    corrupt = evaluate_narrative_gate(
        dossier, _valuation(), tampered, _wave(),
        decided_at=NOW + timedelta(seconds=1),
    )

    assert wrong.status is GateStatus.REJECT
    assert "current_wave_token_mismatch" in wrong.reasons
    assert "current_wave_replaced_research_signal" in wrong.reasons
    assert corrupt.status is GateStatus.REJECT
    assert "research_dossier_hash_mismatch" in corrupt.reasons
    assert "research_identity_invalid" in corrupt.reasons
