from __future__ import annotations

from concurrent.futures import Future
from dataclasses import replace
from pathlib import Path

from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.collection import NarrativeCollector
from debot4.v6.narrative.job_queue import NarrativeJobQueue
from debot4.v6.narrative.mint_alert_coordinator import MintAlertCoordinator
from debot4.v6.narrative.mint_alert_gate import MintAlertGate
from debot4.v6.narrative.mint_alert_policy import MintAlertAction
from debot4.v6.narrative.mint_alert_store import MintAlertStore
from debot4.v6.narrative.mint_location_store import MintLocationStore
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_OBSERVED_AT,
    budujin_match,
    budujin_mint,
    budujin_post,
)
from tests.v6_mint_alert_qualification import qualification


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


class _ApprovingQualifier:
    def qualify(self, match):
        return qualification(match, completed_at=BUDUJIN_OBSERVED_AT)


class _ManualExecutor:
    def __init__(self) -> None:
        self.pending: tuple[Future, object, tuple[object, ...]] | None = None

    def submit(self, function, *args):
        future = Future()
        self.pending = (future, function, args)
        return future

    def complete(self) -> None:
        assert self.pending is not None
        future, function, args = self.pending
        self.pending = None
        future.set_result(function(*args))

    def shutdown(self, **_kwargs) -> None:
        return None


def test_collector_harvests_async_spark_result_on_next_debot_tick(
    tmp_path: Path,
) -> None:
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )
    executor = _ManualExecutor()
    coordinator = MintAlertCoordinator(
        MintAlertGate(
            tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
        ),
        _ApprovingQualifier(),
        clock=lambda: BUDUJIN_OBSERVED_AT,
        executor=executor,
    )
    try:
        with (
            NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue,
            MintLocationStore(tmp_path / "locations.sqlite3") as locations,
            MintAlertStore(
                tmp_path / "alerts.sqlite3",
                clock=lambda: BUDUJIN_OBSERVED_AT,
            ) as alerts,
        ):
            collector = NarrativeCollector(
                _XSource(), object(), object(), queue,
                mint_monitor=_MintSource(), catalyst_mints=state,
                mint_alert_gate=coordinator, mint_locations=locations,
                mint_alerts=alerts, clock=lambda: BUDUJIN_OBSERVED_AT,
            )

            assert collector.collect_mints_once() == ()
            assert collector.collect_x_once() == (budujin_post(),)
            assert alerts.snapshot()["total"] == 0
            assert coordinator.snapshot()["qualification_inflight"] is True

            executor.complete()
            assert collector.collect_mints_once()

            assert alerts.snapshot()["total"] == 1
            snapshot = coordinator.snapshot()
            assert snapshot["qualification_completed"] == 1
            assert snapshot["qualification_waiting"] == 0
    finally:
        coordinator.close()


def test_completed_qualification_is_not_lost_when_another_match_arrives(
    tmp_path: Path,
) -> None:
    first = budujin_match()
    status_id = "2088277816865604999"
    status_url = f"https://x.com/flapdotsh/status/{status_id}"
    second = replace(
        first,
        exact_ca="0x1111111111111111111111111111111111177777",
        catalyst_tweet_id=status_id,
        token_social_urls=(status_url,),
        token_status_url=status_url,
    )
    executor = _ManualExecutor()
    coordinator = MintAlertCoordinator(
        MintAlertGate(
            tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
        ),
        _ApprovingQualifier(),
        clock=lambda: BUDUJIN_OBSERVED_AT,
        executor=executor,
    )
    try:
        assert coordinator.evaluate((first,))[0].action is MintAlertAction.WAIT
        executor.complete()
        verdicts = coordinator.evaluate((second,))
        actions = {item.match.match_id: item.action for item in verdicts}
        assert actions[first.match_id] is MintAlertAction.ALERT
        assert actions[second.match_id] is MintAlertAction.WAIT
    finally:
        coordinator.close()
