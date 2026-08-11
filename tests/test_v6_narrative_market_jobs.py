from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from debot4.v6.narrative.job_payloads import (
    PASSIVE_MARKET_ANOMALY,
    decode_job_input,
    encode_job_input,
)
from debot4.v6.narrative.job_priority import narrative_job_priority
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.market_signal import MarketAnomaly
from debot4.v6.narrative.worker import NarrativeResearchWorker


NOW = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


def _anomaly(**changes: object) -> MarketAnomaly:
    values = {
        "exact_ca": TOKEN,
        "observed_at": NOW,
        "symbol": "DOGO",
        "name": "Dogo",
        "h1_change_pct": Decimal("5.14"),
        "liquidity_usd": Decimal("170800"),
        "valuation_usd": Decimal("2200000"),
        "volume_h1_usd": Decimal("45000"),
        "txns_h1": 120,
        "stage_pct": Decimal("5"),
        "source": "coinmarketcap_datahub",
        "source_url": "https://dapi.coinmarketcap.com/dex/v1/test",
    }
    values.update(changes)
    return MarketAnomaly(**values)


class Runtime:
    def __init__(self) -> None:
        self.market: list[MarketAnomaly] = []

    def research_market_anomaly(self, anomaly: MarketAnomaly) -> None:
        self.market.append(anomaly)

    def research_active_post(self, _post: object) -> None:
        raise AssertionError("wrong route")

    def research_telegram_post(self, _post: object) -> None:
        raise AssertionError("wrong route")

    def research_debot_signal(self, _signal: object, *, anomaly=None) -> None:
        raise AssertionError("wrong route")


def test_market_job_round_trip_and_realtime_priority() -> None:
    value = _anomaly()
    job_id, kind, _digest, document = encode_job_input(value)
    decoded_kind, decoded = decode_job_input(document)

    assert job_id.startswith("narrative-job-")
    assert kind == decoded_kind == PASSIVE_MARKET_ANOMALY
    assert decoded == value
    assert narrative_job_priority(value, now=NOW) == 8
    assert narrative_job_priority(value, now=NOW + timedelta(minutes=3)) == 80


def test_refetch_dedupes_by_stage_identity_and_worker_routes_market(
    tmp_path: Path,
) -> None:
    first = _anomaly()
    refreshed = replace(
        first,
        h1_change_pct=Decimal("8.9"),
        volume_h1_usd=Decimal("90000"),
        liquidity_usd=Decimal("180000"),
    )
    runtime = Runtime()
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3", clock=lambda: NOW) as queue:
        job_id = queue.enqueue(first, priority=8)
        assert queue.enqueue(refreshed, priority=7) == job_id
        assert queue.counts()[JobStatus.PENDING] == 1

        cycle = NarrativeResearchWorker(queue, runtime).work_once()
        assert cycle.status is JobStatus.DONE
        assert runtime.market == [refreshed]
