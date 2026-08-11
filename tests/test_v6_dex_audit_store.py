from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import sqlite3
from urllib.request import urlopen

import pytest

from debot4.v6.dashboard import Dashboard
from debot4.v6.dex_audit.coverage import CoverageReader
from debot4.v6.dex_audit.models import Board, Gainer, HttpAttempt
from debot4.v6.dex_audit.query import audit_snapshot
from debot4.v6.dex_audit.store import AuditStore
from debot4.v6.ledger import V6Ledger


UTC = timezone.utc
START = datetime(2026, 8, 1, tzinfo=UTC)
TOKENS = tuple(f"0x{number:040x}" for number in range(1, 4))


@dataclass
class Clock:
    value: datetime = START

    def __call__(self) -> datetime:
        return self.value


def at(seconds: int) -> datetime:
    return START + timedelta(seconds=seconds)


def micros(value: datetime) -> int:
    return int(value.timestamp() * 1_000_000)


def block_hash(number: int) -> str:
    return "0x" + f"{number:064x}"


def seed(ledger: V6Ledger, clock: Clock, number: int, seconds: int) -> None:
    clock.value = at(seconds)
    ledger.record_candidate_with_signal(
        candidate_id=f"candidate-{number}",
        chain="BSC",
        token_address=TOKENS[number - 1].upper(),
        detected_at=at(seconds - 3),
        candidate_available_at=at(seconds - 2),
        signal_id=f"signal-{number}",
        signal_event_at=at(seconds - 1),
        signal_available_at=at(seconds),
        signal_kind="kol_buy",
        source="debot:test",
        evidence_uri="evidence://test",
    )


def create_ledger(path) -> None:
    clock = Clock()
    with V6Ledger(path, clock=clock) as ledger:
        seed(ledger, clock, 1, 10)
        seed(ledger, clock, 2, 20)
        clock.value = at(22)
        ledger.record_entry_decision(
            decision_id="decision-2",
            candidate_id="candidate-2",
            signal_id="signal-2",
            decided_at=at(21),
            status="reject",
            reason="narrative not verified",
            source="v6:test",
            strategy_version="v6",
        )
        seed(ledger, clock, 3, 30)
        clock.value = at(33)
        ledger.commit_simulated_buy(
            buy_id="buy-3",
            decision_id="decision-3",
            candidate_id="candidate-3",
            signal_id="signal-3",
            decided_at=at(31),
            executed_at=at(32),
            reason="verified narrative",
            strategy_version="v6",
            block_number=100,
            block_hash=block_hash(100),
            parent_block_hash=block_hash(99),
            entry_fdv_usd="100000",
            notional_usd="10",
            entry_position_value_usd="10",
            source="v6:test",
            evidence_uri="evidence://test",
        )


def gainer(number: int, change: int) -> Gainer:
    return Gainer(
        token_address=TOKENS[number - 1],
        pair_address=f"0x{number + 100:040x}",
        symbol=f"T{number}",
        name=f"Token {number}",
        h1_change_pct=Decimal(change),
        liquidity_usd=Decimal("50000"),
        fdv_usd=Decimal("100000"),
        market_cap_usd=Decimal("90000"),
        price_usd=Decimal("0.001"),
        volume_h1_usd=Decimal("10000"),
        txns_h1=20,
    )


def board() -> Board:
    attempt = HttpAttempt(
        source="coinmarketcap_datahub",
        method="POST",
        url="https://dapi.coinmarketcap.com/dex/v1/tokens/gainer-loser/list",
        request_json="{}",
        started_at_us=micros(at(59)),
        completed_at_us=micros(at(60)),
        latency_ms=1000,
        http_status=200,
        response_bytes=1234,
        success=True,
        failure_reason=None,
    )
    return Board(
        as_of_us=micros(at(60)),
        source="coinmarketcap_datahub",
        source_url=attempt.url,
        universe="bsc_1h_gainers_min_liquidity_25000",
        ranking_exact=True,
        rows=(gainer(1, 30), gainer(2, 20), gainer(3, 10)),
        attempts=(attempt,),
    )


def populate(tmp_path):
    ledger_path = tmp_path / "ledger.sqlite3"
    audit_path = tmp_path / "audit.sqlite3"
    create_ledger(ledger_path)
    coverage = CoverageReader(ledger_path).read(board().rows, as_of_us=micros(at(60)))
    with AuditStore(audit_path, clock_us=lambda: micros(at(61))) as store:
        stored = store.append(run_id="run-1", board=board(), coverage=coverage)
    return ledger_path, audit_path, stored, coverage


def test_point_in_time_coverage_and_append_only_projection(tmp_path) -> None:
    ledger_path, audit_path, stored, coverage = populate(tmp_path)

    assert stored.row_count == 3
    assert [row.miss_reason for row in coverage.rows] == [
        "signal_without_decision",
        "decision_reject",
        "covered_by_buy",
    ]
    snapshot = audit_snapshot(audit_path)
    assert snapshot["summary"]["debot_discovered"] == 3
    assert snapshot["summary"]["debot_decided"] == 2
    assert snapshot["summary"]["debot_bought"] == 1
    assert snapshot["summary"]["buy_coverage_pct"] == 33.33
    assert snapshot["rows"][0]["h1_change_pct"] == "30"
    assert snapshot["attempts"][0]["latency_ms"] == 1000

    before_decision = CoverageReader(ledger_path).read(
        (gainer(2, 20),), as_of_us=micros(at(21))
    )
    assert before_decision.rows[0].discovered
    assert not before_decision.rows[0].decided
    assert before_decision.rows[0].miss_reason == "signal_without_decision"

    connection = sqlite3.connect(audit_path)
    try:
        with pytest.raises(sqlite3.IntegrityError, match="UPDATE is forbidden"):
            connection.execute("UPDATE dex_audit_rows SET rank=9")
    finally:
        connection.close()


def test_dashboard_exposes_dex_audit_without_a_buy_input(tmp_path) -> None:
    ledger_path, audit_path, _, _ = populate(tmp_path)

    class State:
        @staticmethod
        def snapshot() -> dict[str, str]:
            return {"status": "test"}

    dashboard = Dashboard(
        "127.0.0.1", 0, ledger_path, State(), audit_database=audit_path
    )
    dashboard.start()
    try:
        host, port = dashboard.address
        with urlopen(f"http://{host}:{port}/api/dex-audit", timeout=2) as response:
            payload = json.load(response)
        assert payload["summary"]["row_count"] == 3
        assert payload["rows"][2]["debot_bought"] is True
    finally:
        dashboard.close()
