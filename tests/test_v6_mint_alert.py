from __future__ import annotations

from datetime import datetime, timedelta
from io import StringIO
import json
from pathlib import Path

import pytest

from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.collection import NarrativeCollector
from debot4.v6.narrative.job_queue import NarrativeJobQueue
from debot4.v6.narrative.live_signal_filter import BscRealtimeSignalFilter
from debot4.v6.narrative.mint_alert_delivery import (
    JsonLineMintAlertSink,
    MintAlertDispatcher,
)
from debot4.v6.narrative.mint_alert_status import read_mint_alert_status
from debot4.v6.narrative.mint_alert_store import MintAlertStore
from debot4.v6.narrative.mint_location_store import MintLocationStore
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_CA,
    BUDUJIN_DELIVERED_AT,
    BUDUJIN_OBSERVED_AT,
    BUDUJIN_RAW_CA,
    BUDUJIN_STATUS,
    budujin_match,
    budujin_mint,
    budujin_post,
    budujin_raw_location,
)


def test_budujin_replay_alerts_tweet_bound_ca_not_earlier_raw_ca(
    tmp_path: Path,
) -> None:
    stream = StringIO()
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )
    with (
        MintLocationStore(tmp_path / "locations.sqlite3") as locations,
        MintAlertStore(
            tmp_path / "alerts.sqlite3", clock=lambda: BUDUJIN_OBSERVED_AT
        ) as alerts,
    ):
        locations.record((budujin_raw_location(),))
        assert alerts.snapshot()["total"] == 0
        assert state.observe_mints((budujin_mint(),)) == ()
        (match,) = state.observe_posts((budujin_post(),))
        assert BscRealtimeSignalFilter(
            clock=lambda: BUDUJIN_OBSERVED_AT
        ).decide(match).accepted
        (alert,) = alerts.record((match,)).created
        assert alert.exact_ca == BUDUJIN_CA
        assert alert.exact_ca != BUDUJIN_RAW_CA
        dispatcher = MintAlertDispatcher(
            alerts, JsonLineMintAlertSink(stream),
            clock=lambda: BUDUJIN_DELIVERED_AT,
        )
        assert dispatcher.dispatch_once().delivered == 1

    payload = json.loads(stream.getvalue())
    assert payload["exact_ca"] == BUDUJIN_CA
    assert payload["token"]["symbol"] == "不对劲"
    assert payload["token"]["stage"] == "completing"
    assert payload["catalyst"]["tweet_id"] == BUDUJIN_STATUS
    assert payload["detection_latency_seconds"] == 13
    assert payload["delivery_latency_seconds"] == 14
    assert payload["triggered_by_raw_mint"] is False
    assert payload["rpc_on_critical_path"] is False
    status = read_mint_alert_status(tmp_path / "alerts.sqlite3")
    assert status["total"] == status["delivered"] == 1
    assert status["detection_sla_met"] == status["delivery_sla_met"] == 1


class _MintSource:
    def __init__(self, mint: object) -> None:
        self.mint = mint

    def poll_once(self, accept=None):
        values = (self.mint,)
        if accept is not None:
            accept(values)
        return values


class _ChainSource:
    poll_seconds = 0.05

    def poll_once(self, accept=None):
        values = (budujin_raw_location(),)
        if accept is not None:
            accept(values)
        return values


def test_raw_chain_and_unlinked_debot_mints_never_alert(tmp_path: Path) -> None:
    unlinked = budujin_mint(exact_ca=BUDUJIN_RAW_CA, linked=False)
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )
    with (
        NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue,
        MintLocationStore(tmp_path / "locations.sqlite3") as locations,
        MintAlertStore(tmp_path / "alerts.sqlite3") as alerts,
    ):
        collector = NarrativeCollector(
            object(), object(), object(), queue,
            mint_monitor=_MintSource(unlinked), catalyst_mints=state,
            chain_mint_monitor=_ChainSource(), mint_locations=locations,
            mint_alerts=alerts,
        )
        assert collector.collect_mints_once() == ()
        assert collector.collect_chain_mints_once() == (budujin_raw_location(),)
        assert locations.snapshot()["observations"] == 2
        assert alerts.snapshot()["total"] == 0
        with pytest.raises(TypeError, match="CatalystMintMatch"):
            alerts.record((budujin_raw_location(),))  # type: ignore[arg-type]


class _BrokenQueue:
    def enqueue(self, payload, **_kwargs):
        if isinstance(payload, CatalystMintMatch):
            raise OSError("queue interrupted")
        return True


class _XSource:
    def monitor_once(self, accept=None):
        values = (budujin_post(),)
        if accept is not None:
            accept(values)
        return values


def test_alert_is_durable_before_research_queue_failure(tmp_path: Path) -> None:
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )
    with (
        MintLocationStore(tmp_path / "locations.sqlite3") as locations,
        MintAlertStore(
            tmp_path / "alerts.sqlite3", clock=lambda: BUDUJIN_OBSERVED_AT
        ) as alerts,
    ):
        collector = NarrativeCollector(
            _XSource(), object(), object(), _BrokenQueue(),
            mint_monitor=_MintSource(budujin_mint()), catalyst_mints=state,
            mint_locations=locations, mint_alerts=alerts,
            signal_filter=BscRealtimeSignalFilter(
                clock=lambda: BUDUJIN_OBSERVED_AT
            ),
            clock=lambda: BUDUJIN_OBSERVED_AT,
        )
        collector.collect_x_once()
        with pytest.raises(OSError, match="queue interrupted"):
            collector.collect_mints_once()
        assert alerts.snapshot()["pending_delivery"] == 1
        assert state.observe_mints(()) == (budujin_match(),)


class _FlakySink:
    def __init__(self) -> None:
        self.calls = 0

    def send(self, _alert: object, *, delivered_at: datetime) -> None:
        del delivered_at
        self.calls += 1
        if self.calls == 1:
            raise ConnectionError("temporary delivery failure")


def test_failed_delivery_retries_without_losing_alert(tmp_path: Path) -> None:
    later = BUDUJIN_DELIVERED_AT + timedelta(seconds=1)
    times = iter((
        BUDUJIN_DELIVERED_AT, BUDUJIN_DELIVERED_AT, later, later,
    ))
    ticks = iter((0.0, 1.0))
    sink = _FlakySink()
    with MintAlertStore(
        tmp_path / "alerts.sqlite3", clock=lambda: BUDUJIN_OBSERVED_AT
    ) as alerts:
        alerts.record((budujin_match(),))
        dispatcher = MintAlertDispatcher(
            alerts, sink, retry_seconds=0.25,
            timer=lambda: next(ticks), clock=lambda: next(times),
        )
        assert dispatcher.dispatch_once().failed == 1
        assert dispatcher.dispatch_once().delivered == 1
    recent = read_mint_alert_status(
        tmp_path / "alerts.sqlite3"
    )["recent_alerts"][0]
    assert recent["delivery_attempts"] == 2
    assert recent["last_delivery_error_type"] is None
