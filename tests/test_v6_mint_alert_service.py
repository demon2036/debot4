from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Event, Thread

from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.job_queue import NarrativeJobQueue
from debot4.v6.narrative.live_signal_filter import BscRealtimeSignalFilter
from debot4.v6.narrative.mint_alert_delivery import MintAlertDispatcher
from debot4.v6.narrative.mint_alert_gate import MintAlertGate
from debot4.v6.narrative.mint_alert_store import MintAlertStore
from debot4.v6.narrative.mint_location_store import MintLocationStore
from debot4.v6.narrative.service import NarrativeService, NarrativeServiceConfig
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_CA,
    BUDUJIN_DELIVERED_AT,
    BUDUJIN_OBSERVED_AT,
    budujin_mint,
    budujin_post,
)


class _XSource:
    def monitor_once(self, accept=None):
        values = (budujin_post(),)
        if accept is not None:
            accept(values)
        return values


class _MintSource:
    def poll_once(self, accept=None):
        values = (budujin_mint(),)
        if accept is not None:
            accept(values)
        return values


class _EmptySource:
    def monitor_once(self, accept=None):
        if accept is not None:
            accept(())
        return ()


class _EmptyDeBot:
    def poll_once(self, *, anomaly=None, accept=None):
        del anomaly
        if accept is not None:
            accept(())
        return ()


class _BlockedResearch:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def _block(self, _value, **_kwargs) -> None:
        self.started.set()
        assert self.release.wait(2)

    research_active_post = _block
    research_catalyst_mint = _block
    research_telegram_post = _block
    research_debot_signal = _block
    research_market_anomaly = _block


class _CapturingSink:
    def __init__(self) -> None:
        self.sent = Event()
        self.exact_cas: list[str] = []

    def send(self, alert: object, *, delivered_at: datetime) -> None:
        del delivered_at
        self.exact_cas.append(alert.exact_ca)
        self.sent.set()


def test_service_delivers_alert_while_research_model_is_blocked(
    tmp_path: Path,
) -> None:
    runtime, sink, stop = _BlockedResearch(), _CapturingSink(), Event()
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )
    with (
        NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue,
        MintLocationStore(tmp_path / "locations.sqlite3") as locations,
        MintAlertStore(
            tmp_path / "alerts.sqlite3", clock=lambda: BUDUJIN_OBSERVED_AT
        ) as alerts,
    ):
        dispatcher = MintAlertDispatcher(
            alerts, sink, poll_seconds=0.05,
            clock=lambda: BUDUJIN_DELIVERED_AT,
        )
        service = NarrativeService(
            monitor=_XSource(), telegram_monitor=_EmptySource(),
            debot_feed=_EmptyDeBot(), mint_monitor=_MintSource(),
            catalyst_mints=state, mint_locations=locations,
            mint_alert_gate=MintAlertGate(
                tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
            ),
            mint_alerts=alerts, mint_alert_dispatcher=dispatcher,
            queue=queue, research_runtime=runtime,
            signal_filter=BscRealtimeSignalFilter(
                clock=lambda: BUDUJIN_OBSERVED_AT
            ),
            clock=lambda: BUDUJIN_OBSERVED_AT,
            config=NarrativeServiceConfig(
                collector_seconds=0.05, worker_idle_seconds=0.01,
            ),
        )
        runner = Thread(target=service.run, args=(stop,))
        runner.start()
        try:
            assert runtime.started.wait(1)
            assert sink.sent.wait(1)
        finally:
            runtime.release.set()
            stop.set()
            runner.join(3)
        assert not runner.is_alive()
        assert sink.exact_cas == [BUDUJIN_CA]
        assert alerts.snapshot()["delivered"] == 1
