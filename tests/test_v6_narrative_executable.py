from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from debot4.v6.narrative import (
    Canonicality,
    ConsensusStage,
    CurrentSignalBoundary,
    DeBotNarrativeContext,
    Dimension,
    EvidenceItem,
    EvidenceRole,
    EvidenceSource,
    FindingState,
    FxTwitterTweet,
    HistoricalKolFact,
    Readiness,
    ReadinessPolicy,
    ResearchOutcome,
    StatusResearch,
    TokenRef,
    build_executable_dossier,
    build_live_dossier,
    evaluate_readiness,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = TokenRef("bsc", "0x1111111111111111111111111111111111111111")
OTHER = "0x2222222222222222222222222222222222222222"
STATUS_ID = "1234567890"
EVENT = NOW - timedelta(seconds=10)
AVAILABLE = NOW - timedelta(seconds=9)

def _tweet() -> FxTwitterTweet:
    text = (
        "Official launch: meet Pandi, Binance red panda mascot meme. "
        f"Official CA: {TOKEN.address}"
    )
    return FxTwitterTweet(
        STATUS_ID, "origin", "author-1", text,
        NOW - timedelta(minutes=10), NOW - timedelta(minutes=8),
        f"https://x.com/origin/status/{STATUS_ID}",
    )


def _history() -> HistoricalKolFact:
    event = NOW - timedelta(minutes=5)
    event_ms = int(event.timestamp() * 1000)
    provider = {
        "evidence_contract_version": 1,
        "qualified": True,
        "is_kol_buy": True,
        "status": "provider_ui_asserted",
        "reason": "provider_ui_buy_with_windowed_wallet_trades",
        "verification_level": "provider_ui_asserted",
        "chain_verified": False,
        "provider_channel_id": "2",
        "provider_group_name": "KOL#3min#30K#300",
        "provider_event_time_ms": event_ms,
        "buy_semantics_source": "debot.v6.parser.windowed_kol_wallet_trades",
        "kol_wallet_count": 3,
        "kol_wallet_identifiers": [
            {"provider_wallet_alias": "KOL-a1b2", "provider_trade_time_ms": event_ms - 1_000},
            {"provider_wallet_alias": "KOL-c3d4", "provider_trade_time_ms": event_ms - 30_000},
            {"provider_wallet_alias": "KOL-e5f6", "provider_trade_time_ms": event_ms - 120_000},
        ],
    }
    metadata = {
        "schema": "debot.v6.kol_buy_evidence.v1",
        "signal_group": "KOL",
        "provider_kol_buy_evidence": provider,
    }
    return HistoricalKolFact(
        "kol:prior", TOKEN.address, "prior", event,
        event + timedelta(seconds=1), event + timedelta(seconds=2),
        event + timedelta(seconds=3), "debot:bsc:official-signal",
        json.dumps(metadata),
    )


def _base():
    tweet = _tweet()
    research = StatusResearch(
        TOKEN, ResearchOutcome.FETCHED, "exact_status_fetched", "lead:1",
        tweet.canonical_url, "origin", STATUS_ID,
        NOW - timedelta(minutes=9), tweet,
    )
    return build_live_dossier(
        TOKEN, research, (_history(),), decision_time=NOW,
        current_signal=CurrentSignalBoundary("current", EVENT, AVAILABLE),
    )


def _context(**changes: object) -> DeBotNarrativeContext:
    description = "Pandi is the Binance red panda mascot community meme."
    values = {
        "token_address": TOKEN.address,
        "signal_id": "current",
        "signal_kind": "kol",
        "group_name": "KOL#3min#30K#300",
        "event_at": EVENT,
        "available_at": AVAILABLE,
        "token_name": "Pandi",
        "token_symbol": "PANDI",
        "description": description,
        "narrative_urls": ("https://x.com/origin",),
        "wallet_aliases": ("KOL-a1b2", "KOL-c3d4", "KOL-e5f6"),
        "kol_buy_qualified": True,
        "kol_buy_reason": "provider_ui_buy_with_windowed_wallet_trades",
        "raw_context": {
            "profile": {"name": "Pandi", "symbol": "PANDI"},
            "social": {"description": description, "twitter": "https://x.com/origin"},
        },
    }
    values.update(changes)
    return DeBotNarrativeContext(**values)


def _spread() -> tuple[EvidenceItem, ...]:
    def item(evidence_id: str, actor: str) -> EvidenceItem:
        return EvidenceItem(
            evidence_id,
            EvidenceSource.COMMUNITY,
            EvidenceRole.PROPAGATION,
            f"Independent community {actor} is discussing the Pandi narrative",
            NOW - timedelta(minutes=7),
            NOW - timedelta(minutes=6),
            NOW - timedelta(minutes=5),
            TOKEN.address,
            actor,
            evidence_id,
            False,
            f"community:{actor}",
        )

    return item("spread:one", "community-one"), item("spread:two", "community-two")


def _readiness(
    context: DeBotNarrativeContext,
    *,
    propagation_evidence: tuple[EvidenceItem, ...] = (),
):
    built = build_executable_dossier(
        _base(), context, propagation_evidence=propagation_evidence,
    )
    decision = evaluate_readiness(
        built.dossier,
        policy=ReadinessPolicy(require_bounded_valuation=False),
    )
    return built, decision


def test_executable_fixture_resolves_every_required_narrative_dimension() -> None:
    built, decision = _readiness(_context(), propagation_evidence=_spread())

    assert decision.status is Readiness.PASS_TO_EXECUTION
    assert built.dossier.canonicality is Canonicality.CREATOR_CLAIMED
    assert built.dossier.fatal_unknowns == ()
    assert built.research.identity_valid


def test_unqualified_current_kol_wave_waits_instead_of_guessing() -> None:
    built, decision = _readiness(_context(
        wallet_aliases=("KOL-a1b2", "KOL-c3d4"),
    ), propagation_evidence=_spread())

    assert decision.status is Readiness.WAIT
    assert "current_capital_confirmation_unverified" in built.dossier.fatal_unknowns
    assert built.dossier.effective_state(Dimension.PROPAGATION) is FindingState.SUPPORTED


def test_conflicting_debot_contract_context_is_an_explicit_reject() -> None:
    description = f"Fake unofficial contract {OTHER}; do not trust this token."
    built, decision = _readiness(_context(
        description=description,
        raw_context={
            "profile": {"name": "Pandi", "symbol": "PANDI"},
            "social": {"description": description, "twitter": "https://x.com/origin"},
        },
    ))

    assert decision.status is Readiness.REJECT
    assert built.dossier.canonicality is Canonicality.CONTRADICTED
    assert "leader_competition_contradicted" in decision.reasons


def test_historical_and_current_kol_buys_do_not_prove_narrative_spread() -> None:
    built, decision = _readiness(_context())

    assert decision.status is Readiness.WAIT
    assert built.dossier.stage is ConsensusStage.DISCOVERY
    assert built.dossier.effective_state(Dimension.PROPAGATION) is FindingState.UNKNOWN
    assert built.dossier.effective_state(Dimension.CONSENSUS_STAGE) is FindingState.UNKNOWN
    restricted_roles = {item.role for item in built.dossier.evidence
                        if item.source in {EvidenceSource.KOL, EvidenceSource.DEBOT}}
    assert restricted_roles == {EvidenceRole.CAPITAL_CONFIRMATION}
