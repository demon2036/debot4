from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from debot4.v6.narrative import (
    CurrentSignalBoundary,
    HistoricalKolFact,
    LiveNarrativeRepository,
    FxTwitterTweet,
    ResearchOutcome,
    ResearchStatus,
    StatusResearch,
    TokenRef,
    build_live_dossier,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = TokenRef("bsc", "0x1111111111111111111111111111111111111111")
OTHER = TokenRef("bsc", "0x2222222222222222222222222222222222222222")
CURRENT = CurrentSignalBoundary(
    "current", NOW - timedelta(seconds=10), NOW - timedelta(seconds=9)
)
STATUS_ID = "1234567890"


class Fetcher:
    def __init__(self, tweet: FxTwitterTweet | None = None) -> None:
        self.tweet = tweet or _tweet()
        self.calls: list[str] = []

    def fetch_status(self, url: str) -> FxTwitterTweet:
        self.calls.append(url)
        return self.tweet


def _tweet(
    text: str = f"Official CA: {TOKEN.address}",
    *,
    fetched_at: datetime = NOW - timedelta(seconds=30),
) -> FxTwitterTweet:
    return FxTwitterTweet(
        STATUS_ID, "origin", "author-1", text,
        NOW - timedelta(minutes=5), fetched_at,
        f"https://x.com/origin/status/{STATUS_ID}",
    )


def _context() -> dict[str, object]:
    return {
        "schema": "debot.token_context.v1",
        "trust": "unverified_provider_metadata",
        "research_leads": {
            "twitter_url": f"https://x.com/origin/status/{STATUS_ID}?s=20"
        },
    }


def _research(
    text: str = f"Official CA: {TOKEN.address}",
    *,
    fetched_at: datetime = NOW - timedelta(seconds=30),
) -> StatusResearch:
    tweet = _tweet(text, fetched_at=fetched_at)
    return StatusResearch(
        TOKEN, ResearchOutcome.FETCHED, "exact_status_fetched", "lead:1",
        tweet.canonical_url, "origin", STATUS_ID, NOW - timedelta(minutes=4), tweet,
    )


def _fact(
    signal_id: str = "prior",
    *,
    inserted_at: datetime = NOW - timedelta(minutes=2),
) -> HistoricalKolFact:
    event = NOW - timedelta(minutes=3)
    available = event + timedelta(seconds=1)
    qualified = event + timedelta(seconds=2)
    event_ms = int(event.timestamp() * 1000)
    metadata = {
        "schema": "debot.v6.kol_buy_evidence.v1",
        "signal_group": "KOL",
        "provider_kol_buy_evidence": {
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
                {
                    "provider_wallet_alias": "KOL-a1b2",
                    "provider_trade_time_ms": event_ms - 1_000,
                },
                {
                    "provider_wallet_alias": "KOL-c3d4",
                    "provider_trade_time_ms": event_ms - 30_000,
                },
                {
                    "provider_wallet_alias": "KOL-e5f6",
                    "provider_trade_time_ms": event_ms - 120_000,
                },
            ],
        },
    }
    return HistoricalKolFact(
        f"kol:{signal_id}", TOKEN.address, signal_id, event, available, qualified,
        inserted_at, "debot:bsc:official-signal", json.dumps(metadata),
    )


def _build(*facts: HistoricalKolFact, research: StatusResearch | None = None):
    return build_live_dossier(
        TOKEN,
        research or _research(),
        facts,
        decision_time=NOW,
        current_signal=CURRENT,
    )


def test_v6_repository_is_exact_status_only_and_token_bound() -> None:
    fetcher = Fetcher()
    repository = LiveNarrativeRepository(fetcher)
    available = NOW - timedelta(minutes=2)

    first = repository.research(TOKEN, _context(), lead_available_at=available)
    replay = repository.research(TOKEN, _context(), lead_available_at=NOW)
    other = repository.research(OTHER, _context(), lead_available_at=available)

    assert first is replay
    assert first.outcome is ResearchOutcome.FETCHED
    assert other.token == OTHER
    assert fetcher.calls == [
        f"https://x.com/origin/status/{STATUS_ID}",
        f"https://x.com/origin/status/{STATUS_ID}",
    ]


def test_v6_exact_binding_and_strictly_prior_kol_are_ready_but_not_trade() -> None:
    built = _build(_fact())

    assert built.research.status is ResearchStatus.READY
    assert built.research.identity_valid
    assert built.research.historical_kol.qualified
    assert built.research.metadata["authorizes_trade"] is False


def test_v6_current_kol_cannot_self_attest_as_history() -> None:
    built = _build(_fact(CURRENT.signal_id))

    assert built.research.status is ResearchStatus.WAIT
    assert built.research.historical_kol.audit[0].reason == "current_signal_excluded"


def test_v6_history_must_be_known_before_current_signal() -> None:
    built = _build(_fact(inserted_at=CURRENT.available_at))

    assert not built.research.historical_kol.qualified
    assert built.research.historical_kol.audit[0].reason == (
        "fact_not_known_before_current_signal"
    )


def test_v6_bare_ca_waits_and_post_cutoff_fetch_never_counts() -> None:
    bare = _build(_fact(), research=_research(f"look {TOKEN.address}"))
    late = _build(
        _fact(), research=_research(fetched_at=NOW + timedelta(microseconds=1))
    )

    assert bare.research.status is ResearchStatus.WAIT
    assert bare.research.binding.reason == "binding_semantics_unverified"
    assert late.research.status is ResearchStatus.WAIT
    assert late.research.binding.reason == "status_unavailable_at_decision"
