from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
import stat

import pytest

from debot4.v6.domain import DeBotSignal
from debot4.v6.grok.models import GrokSearchAnswer, GrokSearchSource
from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.research_package import (
    NarrativeResearchPackage,
    ResearchMode,
)
from debot4.v6.narrative.research_runtime import NarrativeResearchRuntime
from debot4.v6.narrative.research_store import NarrativeResearchStore
from debot4.v6.x.models import XPost


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"
STATUS_ID = "1890071433214038103"
STATUS_URL = f"https://x.com/cz_binance/status/{STATUS_ID}"


class OneShotMonitor:
    def __init__(self, *posts: XPost) -> None:
        self.posts = tuple(posts)

    def monitor_once(self) -> tuple[XPost, ...]:
        posts, self.posts = self.posts, ()
        return posts


class UnavailableVerifier:
    def verify(self, _url: str) -> None:
        raise RuntimeError("provider offline with private details")


class FakeGrok:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        assert instructions
        self.calls.append(prompt)
        return GrokSearchAnswer(
            "response-1",
            "grok-chat-fast",
            '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
            '"event_role":"catalyst","why_now":"new post","unknowns":[]}',
            (GrokSearchSource(STATUS_URL, "CZ status", "x"),),
            (),
            (STATUS_URL,),
            {"total_tokens": 321},
        )

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        assert prompt and instructions
        return self.search("formatted narrative", instructions=instructions)


def _post(tweet_id: str = STATUS_ID) -> XPost:
    return XPost(
        tweet_id,
        "cz_binance",
        "Broccoli narrative update",
        NOW - timedelta(minutes=1),
        NOW,
    )


def _signal() -> DeBotSignal:
    return DeBotSignal(
        signal_id="signal-42",
        token_address=TOKEN,
        signal_kind="kol",
        group_name="KOL#1min#3",
        event_at=NOW - timedelta(seconds=4),
        available_at=NOW - timedelta(seconds=2),
        channel_id="2",
        pair_address=None,
        dex_name="PancakeSwap",
        token_name="Meme North Star",
        token_symbol="MNS",
        token_decimals=18,
        total_supply=Decimal("1000000000"),
        created_at=None,
        provider_fdv_usd=Decimal("125000"),
        provider_liquidity_usd=Decimal("22000"),
        narrative_urls=(),
        description=None,
        wallet_trades=(),
        kol_buy_qualified=True,
        kol_buy_reason="provider_ui_buy_with_windowed_wallet_trades",
    )


def test_runtime_persists_active_and_passive_research_without_trade_authority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "private" / "research.sqlite3"
    grok = FakeGrok()
    with NarrativeResearchStore(path, clock=lambda: NOW) as store:
        runtime = NarrativeResearchRuntime(
            monitor=OneShotMonitor(_post()),
            grok=grok,
            verifier=UnavailableVerifier(),
            store=store,
            clock=lambda: NOW,
        )

        packages = runtime.run_once((_signal(),))

        assert [item.mode for item in packages] == [
            ResearchMode.PASSIVE_DEBOT,
            ResearchMode.ACTIVE_ACTOR,
        ]
        assert store.count() == 2
        passive, active = (store.get(item.package_id) for item in packages)
        assert passive is not None and active is not None
        assert passive["research"]["result"]["answer"]["text"].startswith("{")
        assert passive["research"]["x_status_leads_are_evidence"] is False
        assert active["reason"] == "runtime_research_failed:RuntimeError"
        for document in (passive, active):
            assert document["research_only"] is True
            assert document["authorizes_trade"] is False
            assert document["execution_directive"] is None
        assert "private details" not in active["reason"]

    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_store_is_atomic_idempotent_and_append_only(tmp_path: Path) -> None:
    package = NarrativeResearchPackage(
        ResearchMode.PASSIVE_DEBOT,
        "trigger-1",
        NOW - timedelta(seconds=1),
        NOW,
        "WAIT",
        "research_pending",
        {"result": {"authorizes_trade": False}},
    )
    path = tmp_path / "research.sqlite3"
    with NarrativeResearchStore(path, clock=lambda: NOW) as store:
        assert store.append(package) is True
        assert store.append(package) is False
        assert store.count() == 1

    connection = sqlite3.connect(path)
    with pytest.raises(sqlite3.IntegrityError, match="UPDATE is forbidden"):
        connection.execute(
            "UPDATE narrative_research_packages SET reason='changed'"
        )
    connection.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="DELETE is forbidden"):
        connection.execute("DELETE FROM narrative_research_packages")
    connection.close()


def test_package_rejects_nested_trade_authority() -> None:
    with pytest.raises(ValueError, match="cannot authorize"):
        NarrativeResearchPackage(
            ResearchMode.ACTIVE_ACTOR,
            "trigger-unsafe",
            NOW - timedelta(seconds=1),
            NOW,
            "READY",
            "unsafe_fixture",
            {"nested": {"authorizes_trade": True}},
        )


def test_active_failures_are_isolated_per_post(tmp_path: Path) -> None:
    second = _post("1890071433214038104")
    with NarrativeResearchStore(tmp_path / "research.sqlite3") as store:
        runtime = NarrativeResearchRuntime(
            monitor=OneShotMonitor(_post(), second),
            grok=FakeGrok(),
            verifier=UnavailableVerifier(),
            store=store,
            clock=lambda: NOW,
        )

        packages = runtime.poll_active()

        assert len(packages) == 2
        assert store.count() == 2
        assert all(item.status == "WAIT" for item in packages)


def test_independent_active_research_propagates_for_queue_retry(
    tmp_path: Path,
) -> None:
    with NarrativeResearchStore(tmp_path / "research.sqlite3") as store:
        runtime = NarrativeResearchRuntime(
            monitor=OneShotMonitor(),
            grok=FakeGrok(),
            verifier=UnavailableVerifier(),
            store=store,
            clock=lambda: NOW,
        )

        with pytest.raises(RuntimeError, match="provider offline"):
            runtime.research_active_post(_post())
        assert store.count() == 0


def test_catalyst_mint_research_uses_its_distinct_audit_mode(
    tmp_path: Path,
) -> None:
    match = CatalystMintMatch(
        exact_ca=TOKEN,
        token_created_at=NOW - timedelta(minutes=1),
        observed_at=NOW - timedelta(seconds=30),
        token_name="bBroker",
        token_symbol="bBroker",
        provider_fdv_usd=Decimal("5000.67"),
        launchpad="flap",
        token_description=None,
        token_social_urls=(STATUS_URL,),
        token_status_url=STATUS_URL,
        catalyst_tweet_id=STATUS_ID,
        catalyst_author="cz_binance",
        catalyst_text="An upstream product catalyst without a CA.",
        catalyst_created_at=NOW - timedelta(minutes=2),
        catalyst_fetched_at=NOW - timedelta(seconds=90),
    )
    with NarrativeResearchStore(tmp_path / "research.sqlite3") as store:
        runtime = NarrativeResearchRuntime(
            monitor=OneShotMonitor(),
            grok=FakeGrok(),
            verifier=UnavailableVerifier(),
            store=store,
            clock=lambda: NOW,
        )

        package = runtime.research_catalyst_mint(match)
        stored = store.get(package.package_id)

        assert package.mode is ResearchMode.PASSIVE_CATALYST_MINT
        assert stored is not None
        assert stored["mode"] == "PASSIVE_CATALYST_MINT"
        assert stored["authorizes_trade"] is False
        trigger = stored["research"]["trigger"]
        assert trigger["exact_ca"] == TOKEN.lower()
        assert trigger["social_urls_are_evidence"] is False
