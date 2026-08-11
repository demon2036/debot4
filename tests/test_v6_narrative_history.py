from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json

from debot4.v6.narrative import (
    CurrentSignalBoundary,
    HistoricalKolFact,
    TokenRef,
    assess_historical_kol_buys,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = TokenRef("bsc", "0x1111111111111111111111111111111111111111")
CURRENT = CurrentSignalBoundary(
    "current", NOW - timedelta(seconds=10), NOW - timedelta(seconds=9)
)


def _fact(metadata: dict[str, object], *, signal_id: str, source: str) -> HistoricalKolFact:
    event = NOW - timedelta(minutes=5)
    return HistoricalKolFact(
        f"kol:{signal_id}", TOKEN.address, signal_id, event,
        event + timedelta(seconds=1), event + timedelta(seconds=2),
        event + timedelta(seconds=3), source, json.dumps(metadata),
    )


def _proxy_metadata() -> dict[str, object]:
    event = NOW - timedelta(minutes=5)
    return {
        "schema": "debot.v6.kol_participation_proxy.v1",
        "signal_group": "KOL_RANKS",
        "provider_kol_participation_proxy": {
            "evidence_contract_version": 1,
            "label": "historical_kol_participation_proxy",
            "kind": "debot_ranks_kol_count_increase",
            "is_wallet_buy": False,
            "is_kol_buy": False,
            "verification_level": "provider_rank_snapshot_delta",
            "chain_verified": False,
            "source_endpoint": "/api/dashboard/meme/v3/ranks",
            "first_observed_time_ms": int(event.timestamp() * 1000),
            "time_source": "client_fetch_completion",
            "provider_token_address": TOKEN.address,
            "previous_kol_count": 1,
            "current_kol_count": 3,
            "increase": 2,
        },
    }


def _assess(fact: HistoricalKolFact):
    return assess_historical_kol_buys(
        TOKEN, (fact,), current_signal=CURRENT, decision_time=NOW
    )


def test_ranks_count_increase_is_accepted_only_as_labeled_proxy() -> None:
    result = _assess(_fact(
        _proxy_metadata(), signal_id="rank:prior", source="debot:bsc:ranks"
    ))

    assert result.qualified
    assert result.qualification_kind == "rank_kol_count_increase_proxy"
    assert result.reason == "historical_kol_participation_proxy_qualified"
    assert "not a wallet-level BUY" in result.evidence[0].claim
    assert result.audit[0].evidence_kind == "rank_kol_count_increase_proxy"


def test_proxy_never_self_attests_and_never_claims_wallet_buy() -> None:
    current = _assess(_fact(
        _proxy_metadata(), signal_id=CURRENT.signal_id, source="debot:bsc:ranks"
    ))
    forged = _proxy_metadata()
    forged["provider_kol_participation_proxy"]["is_kol_buy"] = True
    invalid = _assess(_fact(
        forged, signal_id="rank:prior", source="debot:bsc:ranks"
    ))

    assert not current.qualified
    assert current.audit[0].reason == "current_signal_excluded"
    assert not invalid.qualified
    assert invalid.audit[0].reason == "provider_kol_proxy_contract_invalid"
