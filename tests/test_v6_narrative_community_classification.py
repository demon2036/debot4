from datetime import datetime, timedelta, timezone

from debot4.v6.narrative import (
    Canonicality,
    CurrentSignalBoundary,
    DeBotNarrativeContext,
    Dimension,
    EvidenceItem,
    EvidenceRole,
    EvidenceSource,
    FindingState,
    FxTwitterTweet,
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
EVENT = NOW - timedelta(seconds=10)
AVAILABLE = NOW - timedelta(seconds=9)
STATUS_ID = "1234567890"


def _base():
    tweet = FxTwitterTweet(
        STATUS_ID,
        "origin",
        "author-1",
        "Official launch: meet Pandi, Binance red panda mascot community meme.",
        NOW - timedelta(minutes=10),
        NOW - timedelta(minutes=8),
        f"https://x.com/origin/status/{STATUS_ID}",
    )
    research = StatusResearch(
        TOKEN,
        ResearchOutcome.FETCHED,
        "exact_status_fetched",
        "lead:community",
        tweet.canonical_url,
        "origin",
        STATUS_ID,
        NOW - timedelta(minutes=9),
        tweet,
    )
    return build_live_dossier(
        TOKEN,
        research,
        (),
        decision_time=NOW,
        current_signal=CurrentSignalBoundary("current", EVENT, AVAILABLE),
    )


def _context() -> DeBotNarrativeContext:
    description = "Pandi is the Binance red panda mascot community meme."
    return DeBotNarrativeContext(
        TOKEN.address,
        "current",
        "kol",
        "KOL#3min#30K#300",
        EVENT,
        AVAILABLE,
        "Pandi",
        "PANDI",
        description,
        ("https://x.com/origin",),
        ("KOL-a1b2", "KOL-c3d4", "KOL-e5f6"),
        True,
        "provider_ui_buy_with_windowed_wallet_trades",
        {
            "profile": {"name": "Pandi", "symbol": "PANDI"},
            "social": {
                "description": description,
                "twitter": "https://x.com/origin",
            },
        },
    )


def _spread(
    evidence_id: str,
    source: EvidenceSource,
    group: str,
) -> EvidenceItem:
    return EvidenceItem(
        evidence_id,
        source,
        EvidenceRole.PROPAGATION,
        f"{group} independently discusses the Pandi narrative",
        NOW - timedelta(minutes=7),
        NOW - timedelta(minutes=6),
        NOW - timedelta(minutes=5),
        TOKEN.address,
        group,
        evidence_id,
        source is EvidenceSource.DEBOT,
        group,
    )


def test_community_path_replaces_base_identity_without_duplicate_dimensions() -> None:
    built = build_executable_dossier(_base(), _context())
    decision = evaluate_readiness(
        built.dossier,
        policy=ReadinessPolicy(require_bounded_valuation=False),
    )

    assert decision.status is Readiness.WAIT
    assert built.dossier.canonicality is Canonicality.PROVISIONAL_LEADER
    assert built.dossier.finding(Dimension.ORIGIN).state is FindingState.CONFIRMED
    assert built.dossier.finding(Dimension.LEGITIMACY).state is FindingState.SUPPORTED
    assert len({item.dimension for item in built.dossier.findings}) == len(
        built.dossier.findings
    )


def test_two_independent_community_sources_validate_community_consensus() -> None:
    evidence = (
        _spread("community:one", EvidenceSource.COMMUNITY, "community:one"),
        _spread("community:two", EvidenceSource.COMMUNITY, "community:two"),
    )
    built = build_executable_dossier(
        _base(), _context(), propagation_evidence=evidence
    )

    assert built.dossier.canonicality is Canonicality.COMMUNITY_CONSENSUS
    assert built.dossier.finding(Dimension.PROPAGATION).state is FindingState.SUPPORTED
    assert built.dossier.finding(Dimension.CONSENSUS_STAGE).state is FindingState.SUPPORTED


def test_kol_and_debot_claims_cannot_self_label_as_narrative_spread() -> None:
    claims = (
        _spread("kol:spread", EvidenceSource.KOL, "kol:one"),
        _spread("debot:spread", EvidenceSource.DEBOT, "debot:one"),
    )
    built = build_executable_dossier(
        _base(), _context(), propagation_evidence=claims
    )

    assert built.dossier.finding(Dimension.PROPAGATION).state is FindingState.UNKNOWN
    assert built.dossier.finding(Dimension.CONSENSUS_STAGE).state is FindingState.UNKNOWN
