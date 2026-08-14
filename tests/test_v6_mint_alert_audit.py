from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from debot4.v6.dex_audit.models import Board, Gainer
from debot4.v6.narrative.debot_mint_location import location_from_debot
from debot4.v6.narrative.mint_alert_audit import audit_mint_alerts
from debot4.v6.narrative.mint_alert_audit_reader import (
    read_debot_mints,
    read_mint_alerts,
)
from debot4.v6.narrative.mint_alert_gate import MintAlertGate
from debot4.v6.narrative.mint_alert_gate_codec import read_mint_alert_gate_state
from debot4.v6.narrative.mint_alert_store import MintAlertStore
from debot4.v6.narrative.mint_location_store import MintLocationStore
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_CA,
    BUDUJIN_DELIVERED_AT,
    BUDUJIN_OBSERVED_AT,
    BUDUJIN_POST_AT,
    budujin_match,
    budujin_mint,
)


def _board(*, source: str = "coinmarketcap_datahub", exact: bool = True) -> Board:
    return Board(
        as_of_us=int(BUDUJIN_DELIVERED_AT.timestamp() * 1_000_000),
        source=source,
        source_url="https://example.invalid/market-board",
        universe="bsc_1h",
        ranking_exact=exact,
        rows=(Gainer(
            token_address=BUDUJIN_CA,
            pair_address=None,
            symbol="不对劲",
            name="SEED ALPHA",
            h1_change_pct=Decimal("100"),
            liquidity_usd=Decimal("50000"),
            fdv_usd=Decimal("500000"),
            market_cap_usd=Decimal("500000"),
            price_usd=Decimal("0.01"),
            volume_h1_usd=Decimal("20000"),
            txns_h1=20,
        ),),
        attempts=(),
    )


def _gate_state(path: Path):
    gate = MintAlertGate(path, clock=lambda: BUDUJIN_OBSERVED_AT)
    gate.evaluate((budujin_match(),))
    state = read_mint_alert_gate_state(path)
    assert state is not None
    return state


def test_budujin_replay_is_alerted_and_delivered_within_sla(
    tmp_path: Path,
) -> None:
    gate = _gate_state(tmp_path / "gate.json")
    alert_path = tmp_path / "alerts.sqlite3"
    location_path = tmp_path / "locations.sqlite3"
    with MintAlertStore(
        alert_path, clock=lambda: BUDUJIN_OBSERVED_AT
    ) as alerts:
        write = alerts.record((budujin_match(),))
        alerts.mark_delivered(write.created[0].alert_id, BUDUJIN_DELIVERED_AT)
    with MintLocationStore(location_path) as locations:
        locations.record((location_from_debot(budujin_mint()),))

    report = audit_mint_alerts(
        gate,
        read_mint_alerts(alert_path, since=gate.policy_started_at),
        read_debot_mints(location_path, since=gate.policy_started_at),
        _board(),
        now=BUDUJIN_DELIVERED_AT,
    )

    assert report.healthy is True
    assert report.review_required is False
    assert report.violations == ()
    assert report.market_leads[0].coverage == "alerted"
    assert report.market_leads[0].alert is not None


def test_reader_aggregates_all_debot_stages_for_one_exact_ca(
    tmp_path: Path,
) -> None:
    path = tmp_path / "locations.sqlite3"
    with MintLocationStore(path) as locations:
        locations.record((
            location_from_debot(replace(budujin_mint(), stage="new")),
            location_from_debot(replace(
                budujin_mint(),
                stage="completed",
                fetched_at=BUDUJIN_OBSERVED_AT + timedelta(seconds=2),
            )),
        ))

    (seen,) = read_debot_mints(path, since=BUDUJIN_POST_AT)

    assert seen.exact_ca == BUDUJIN_CA
    assert seen.sources == ("debot_completed", "debot_new")
    assert seen.first_observed_at == BUDUJIN_OBSERVED_AT
    assert seen.last_observed_at == BUDUJIN_OBSERVED_AT + timedelta(seconds=2)


def test_selected_match_without_durable_alert_is_a_hard_violation(
    tmp_path: Path,
) -> None:
    gate = _gate_state(tmp_path / "gate.json")
    report = audit_mint_alerts(
        gate, (), (), _board(),
        now=BUDUJIN_POST_AT + timedelta(seconds=20),
    )

    assert report.healthy is False
    assert {item.code for item in report.violations} == {
        "selected_alert_missing"
    }
    assert report.market_leads[0].coverage == "not_seen_by_debot"
    assert report.review_required is True
    assert report.attention_required is True
    assert report.as_public_dict()["status"] == "attention"


def test_inexact_market_fallback_is_explicitly_unavailable(
    tmp_path: Path,
) -> None:
    gate = _gate_state(tmp_path / "gate.json")
    fallback = _board(source="geckoterminal", exact=False)
    report = audit_mint_alerts(
        gate, (), (), fallback, now=BUDUJIN_DELIVERED_AT
    )

    assert report.market_available is False
    assert report.market_leads == ()
    assert report.market_failure_reason == (
        "exact market board unavailable; received geckoterminal"
    )
    assert report.healthy is False
