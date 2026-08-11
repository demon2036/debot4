from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from threading import Event, Thread

import pytest

from debot4.v6.domain import DeBotSignal
from debot4.v6.narrative.debot_feed import NarrativeDeBotCandidate
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.service import (
    NarrativeCollector,
    NarrativeResearchWorker,
    NarrativeService,
    NarrativeServiceConfig,
)
from debot4.v6.telegram.models import TelegramPost
from debot4.v6.x.models import XPost


NOW = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


def _post(tweet_id: str = "1900000000000000001") -> XPost:
    return XPost(tweet_id, "cz_binance", "A new cultural symbol", NOW, NOW)


def _signal(signal_id: str = "debot-1") -> DeBotSignal:
    return DeBotSignal(
        signal_id=signal_id,
        token_address=TOKEN,
        signal_kind="kol",
        group_name="KOL#1min#3",
        event_at=NOW,
        available_at=NOW,
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
        kol_buy_qualified=True,
        kol_buy_reason="provider KOL signal",
    )


def _telegram(message_id: int = 3749) -> TelegramPost:
    return TelegramPost("Yndegen", message_id, "new meme context", NOW, NOW)


class BatchMonitor:
    def __init__(self, *posts: XPost) -> None:
        self.posts = tuple(posts)
        self.calls = 0
        self.commits = 0
        self.third_call = Event()

    def monitor_once(self, accept=None) -> tuple[XPost, ...]:
        self.calls += 1
        if self.calls >= 3:
            self.third_call.set()
        if accept is not None:
            accept(self.posts)
        self.commits += 1
        return self.posts


class BatchFeed:
    def __init__(self, *signals: DeBotSignal) -> None:
        self.candidates = tuple(
            NarrativeDeBotCandidate(item, ("qualified_kol",)) for item in signals
        )
        self.commits = 0

    def poll_once(self, *, anomaly=None, accept=None):
        if accept is not None:
            accept(self.candidates)
        self.commits += 1
        return self.candidates


class BatchTelegram:
    def __init__(self, *posts: TelegramPost) -> None:
        self.posts = tuple(posts)
        self.commits = 0

    def monitor_once(self, accept=None) -> tuple[TelegramPost, ...]:
        if accept is not None:
            accept(self.posts)
        self.commits += 1
        return self.posts


class FakeRuntime:
    def __init__(self, *, active_failures: int = 0, block: bool = False) -> None:
        self.active_failures = active_failures
        self.active: list[XPost] = []
        self.telegram: list[TelegramPost] = []
        self.passive: list[DeBotSignal] = []
        self.started = Event()
        self.release = Event()
        self.block = block

    def research_active_post(self, post: XPost) -> None:
        self.active.append(post)
        self.started.set()
        if self.block:
            assert self.release.wait(2)
        if self.active_failures:
            self.active_failures -= 1
            raise RuntimeError("temporary Grok failure")

    def research_debot_signal(self, signal: DeBotSignal, *, anomaly=None) -> None:
        self.passive.append(signal)

    def research_telegram_post(self, post: TelegramPost) -> None:
        self.telegram.append(post)


class FakeRealtime:
    def __init__(self) -> None:
        self.started = Event()

    def run(self, stop: Event, accept) -> None:
        accept((_telegram(9001),))
        self.started.set()
        stop.wait(2)


class InterruptingQueue:
    def __init__(self, queue: NarrativeJobQueue) -> None:
        self.queue = queue
        self.calls = 0
        self.interrupt = True

    def enqueue(self, payload, *, max_attempts=3, priority=50):
        self.calls += 1
        if self.interrupt and self.calls == 2:
            raise OSError("queue write interrupted")
        return self.queue.enqueue(
            payload, max_attempts=max_attempts, priority=priority
        )


def test_collector_retries_partial_batches_idempotently_before_checkpoint(
    tmp_path: Path,
) -> None:
    monitor = BatchMonitor(_post(), _post("1900000000000000002"))
    telegram = BatchTelegram(_telegram())
    feed = BatchFeed(_signal())
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        interrupting = InterruptingQueue(queue)
        collector = NarrativeCollector(monitor, telegram, feed, interrupting)

        with pytest.raises(OSError, match="interrupted"):
            collector.collect_once()
        assert monitor.commits == 0 and telegram.commits == 0 and feed.commits == 0
        assert queue.counts()[JobStatus.PENDING] == 1

        interrupting.interrupt = False
        cycle = collector.collect_once()
        assert cycle.x_posts == 2 and cycle.telegram_posts == 1
        assert cycle.debot_signals == 1
        assert monitor.commits == 1 and telegram.commits == 1 and feed.commits == 1
        assert queue.counts()[JobStatus.PENDING] == 4

        collector.collect_once()
        assert queue.counts()[JobStatus.PENDING] == 4


def test_worker_routes_jobs_and_retries_research_failures(tmp_path: Path) -> None:
    runtime = FakeRuntime(active_failures=1)
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        active_id = queue.enqueue(_post(), max_attempts=2)
        worker = NarrativeResearchWorker(
            queue, runtime, retry_delay_seconds=0, worker="test-worker"
        )

        retried = worker.work_once()
        assert retried.job_id == active_id and retried.status is JobStatus.PENDING
        assert retried.attempts == 1
        done = worker.work_once()
        assert done.job_id == active_id and done.status is JobStatus.DONE

        passive_id = queue.enqueue(_signal())
        passive = worker.work_once()
        assert passive.job_id == passive_id and passive.status is JobStatus.DONE
        assert runtime.active == [_post(), _post()]
        assert runtime.passive == [_signal()]
        telegram_id = queue.enqueue(_telegram())
        telegram = worker.work_once()
        assert telegram.job_id == telegram_id and telegram.status is JobStatus.DONE
        assert runtime.telegram == [_telegram()]
        assert queue.counts()[JobStatus.DONE] == 3


def test_service_keeps_collecting_while_grok_worker_is_blocked(tmp_path: Path) -> None:
    monitor = BatchMonitor(_post())
    telegram = BatchTelegram()
    feed = BatchFeed()
    runtime = FakeRuntime(block=True)
    stop = Event()
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        service = NarrativeService(
            monitor=monitor,
            telegram_monitor=telegram,
            debot_feed=feed,
            queue=queue,
            research_runtime=runtime,
            config=NarrativeServiceConfig(
                collector_seconds=0.25,
                worker_idle_seconds=0.01,
                retry_delay_seconds=0,
            ),
        )
        runner = Thread(target=service.run, args=(stop,))
        runner.start()
        assert runtime.started.wait(1)
        assert monitor.third_call.wait(1)
        assert monitor.calls >= 3
        runtime.release.set()
        stop.set()
        runner.join(3)
        assert not runner.is_alive()


def test_service_runs_realtime_telegram_as_an_independent_source(
    tmp_path: Path,
) -> None:
    realtime = FakeRealtime()
    stop = Event()
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        service = NarrativeService(
            monitor=BatchMonitor(),
            telegram_monitor=BatchTelegram(),
            debot_feed=BatchFeed(),
            queue=queue,
            research_runtime=FakeRuntime(),
            telegram_realtime=realtime,
            config=NarrativeServiceConfig(worker_idle_seconds=0.01),
        )
        runner = Thread(target=service.run, args=(stop,))
        runner.start()
        assert realtime.started.wait(1)
        stop.set()
        runner.join(3)
        assert not runner.is_alive()
        assert service.last_realtime_error_type is None


@pytest.mark.parametrize("seconds", [0.01, 2.01, 30.0])
def test_collector_cadence_rejects_slow_or_unbounded_values(seconds: float) -> None:
    with pytest.raises(ValueError, match="collector_seconds"):
        NarrativeServiceConfig(collector_seconds=seconds)


def test_collector_cadence_accepts_fifty_ms_to_two_seconds() -> None:
    assert NarrativeServiceConfig(collector_seconds=0.05).collector_seconds == 0.05
    assert NarrativeServiceConfig(collector_seconds=2.0).collector_seconds == 2.0
