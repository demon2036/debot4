from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.service import NarrativeService, NarrativeServiceConfig
from debot4.v6.x.models import XPost


NOW = datetime(2026, 8, 14, 12, tzinfo=timezone.utc)


class EmptyX:
    def monitor_once(self, accept=None):
        del accept
        return ()


class EmptyTelegram:
    def monitor_once(self, accept=None):
        del accept
        return ()


class EmptyDeBot:
    def poll_once(self, *, anomaly=None, accept=None):
        del anomaly, accept
        return ()


class ConcurrentRuntime:
    def __init__(self) -> None:
        self.lock = Lock()
        self.release = Event()
        self.two_started = Event()
        self.two_done = Event()
        self.active = 0
        self.maximum = 0
        self.completed = 0

    def research_active_post(self, post: XPost) -> None:
        del post
        with self.lock:
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            if self.active == 2:
                self.two_started.set()
        assert self.release.wait(2)
        with self.lock:
            self.active -= 1
            self.completed += 1
            if self.completed == 2:
                self.two_done.set()

    def research_telegram_post(self, post: object) -> None:
        del post

    def research_debot_signal(self, signal: object, *, anomaly=None) -> None:
        del signal, anomaly

    def research_market_anomaly(self, anomaly: object) -> None:
        del anomaly


def _post(tweet_id: str) -> XPost:
    return XPost(tweet_id, "cz_binance", "New event", NOW, NOW)


def test_service_processes_grok_jobs_with_a_bounded_worker_pool(
    tmp_path: Path,
) -> None:
    runtime = ConcurrentRuntime()
    stop = Event()
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        queue.enqueue(_post("2090000000000000001"))
        queue.enqueue(_post("2090000000000000002"))
        service = NarrativeService(
            monitor=EmptyX(),
            telegram_monitor=EmptyTelegram(),
            debot_feed=EmptyDeBot(),
            queue=queue,
            research_runtime=runtime,
            config=NarrativeServiceConfig(
                collector_seconds=0.05,
                worker_idle_seconds=0.01,
                research_workers=2,
            ),
        )
        runner = Thread(target=service.run, args=(stop,))
        runner.start()

        assert runtime.two_started.wait(1)
        assert runtime.maximum == 2
        runtime.release.set()
        assert runtime.two_done.wait(1)
        stop.set()
        runner.join(3)

        assert not runner.is_alive()
        assert len(service.workers) == 2
        assert queue.counts()[JobStatus.DONE] == 2
        assert service.last_worker_error_type is None
