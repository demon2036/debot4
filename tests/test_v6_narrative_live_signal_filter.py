from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from debot4.v6.domain import DeBotSignal
from debot4.v6.narrative.live_signal_filter import BscRealtimeSignalFilter
from debot4.v6.telegram.models import TelegramPost
from debot4.v6.x.models import XPost


NOW = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


def _post(
    author: str,
    text: str,
    *,
    contracts: tuple[str, ...] = (),
) -> XPost:
    return XPost(
        "2090000000000000001",
        author,
        text,
        NOW,
        NOW + timedelta(seconds=2),
        bsc_contracts=contracts,
    )


def _signal(*, age_seconds: float, qualified: bool = False) -> DeBotSignal:
    observed = NOW - timedelta(seconds=age_seconds)
    return DeBotSignal(
        signal_id="live-1",
        token_address=TOKEN,
        signal_kind="kol",
        group_name="KOL#1min#3",
        event_at=observed,
        available_at=observed,
        channel_id="2",
        pair_address=None,
        dex_name="PancakeSwap",
        token_name="Narrative Dog",
        token_symbol="NDOG",
        token_decimals=18,
        total_supply=Decimal("1000000000"),
        created_at=None,
        provider_fdv_usd=Decimal("100000"),
        provider_liquidity_usd=Decimal("20000"),
        narrative_urls=(),
        description=None,
        wallet_trades=(),
        kol_buy_qualified=qualified,
        kol_buy_reason="provider signal",
    )


def test_cz_and_reviewed_catalysts_pass_without_waiting_for_a_mint() -> None:
    policy = BscRealtimeSignalFilter(clock=lambda: NOW)

    cz = policy.decide(_post("cz_binance", "Keep building."))
    jensen = policy.decide(_post("JensenHuang", "The age of robotics."))

    assert cz.accepted and cz.reason == "reviewed_catalyst_event"
    assert jensen.accepted and jensen.reason == "reviewed_catalyst_event"


def test_routine_propagation_chatter_is_dropped_but_actionable_text_passes() -> None:
    policy = BscRealtimeSignalFilter(clock=lambda: NOW)

    routine = policy.decide(_post("only1mrwhite", "Good morning everyone"))
    actionable = policy.decide(_post("only1mrwhite", "I bought $NDOG on BSC"))

    assert not routine.accepted and routine.reason == "routine_x_chatter"
    assert actionable.accepted and actionable.reason == "bsc_actor_actionable"


def test_ticker_without_bsc_context_does_not_send_propagation_kol_to_grok() -> None:
    decision = BscRealtimeSignalFilter(clock=lambda: NOW).decide(
        _post("sunapooh67", "Claimed and sold $LAB")
    )

    assert not decision.accepted and decision.reason == "routine_x_chatter"


def test_exact_bsc_ca_always_passes_even_from_non_bsc_propagator() -> None:
    decision = BscRealtimeSignalFilter(clock=lambda: NOW).decide(
        _post("blknoiz06", "watch this", contracts=(TOKEN,))
    )

    assert decision.accepted and decision.reason == "exact_bsc_ca"


def test_debot_requires_fresh_event_and_availability_times() -> None:
    policy = BscRealtimeSignalFilter(clock=lambda: NOW, debot_fresh_seconds=180)

    assert policy.decide(_signal(age_seconds=30)).reason == "fresh_debot_token_lead"
    stale = policy.decide(_signal(age_seconds=600))
    stale_qualified = policy.decide(replace(
        _signal(age_seconds=600), kol_buy_qualified=True
    ))
    replayed = policy.decide(replace(
        _signal(age_seconds=600), available_at=NOW - timedelta(seconds=5)
    ))
    fresh_qualified = policy.decide(replace(
        _signal(age_seconds=30), kol_buy_qualified=True
    ))

    assert not stale.accepted and stale.reason == "stale_or_unqualified_debot"
    assert not stale_qualified.accepted
    assert not replayed.accepted
    assert fresh_qualified.accepted
    assert fresh_qualified.reason == "qualified_debot_kol"


def test_unregistered_telegram_chatter_fails_closed() -> None:
    post = TelegramPost("randomalpha", 7, "good morning", NOW, NOW)

    decision = BscRealtimeSignalFilter(clock=lambda: NOW).decide(post)

    assert not decision.accepted
    assert decision.reason == "routine_telegram_chatter"
