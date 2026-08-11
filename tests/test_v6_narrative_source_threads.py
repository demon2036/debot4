from __future__ import annotations

from pathlib import Path
from threading import Event, Thread

from debot4.v6.narrative.job_queue import NarrativeJobQueue
from debot4.v6.narrative.service import NarrativeService, NarrativeServiceConfig


class BlockingX:
    def __init__(self) -> None:
        self.started = Event()
        self.release = Event()

    def monitor_once(self, accept=None):
        self.started.set()
        assert self.release.wait(2)
        if accept is not None:
            accept(())
        return ()


class PublicTelegram:
    def __init__(self) -> None:
        self.called = Event()

    def monitor_once(self, accept=None):
        self.called.set()
        if accept is not None:
            accept(())
        return ()


class DeBot:
    def __init__(self) -> None:
        self.called = Event()

    def poll_once(self, *, anomaly=None, accept=None):
        self.called.set()
        if accept is not None:
            accept(())
        return ()


class Market:
    def __init__(self) -> None:
        self.called = Event()

    def poll_once(self, accept=None):
        self.called.set()
        if accept is not None:
            accept(())
        return ()


class Reposts:
    def __init__(self) -> None:
        self.called = Event()

    def poll_once(self):
        self.called.set()
        return ()


class IdleRuntime:
    def research_active_post(self, _post):
        raise AssertionError("queue should be empty")

    def research_telegram_post(self, _post):
        raise AssertionError("queue should be empty")

    def research_debot_signal(self, _signal, *, anomaly=None):
        raise AssertionError("queue should be empty")

    def research_market_anomaly(self, _anomaly):
        raise AssertionError("queue should be empty")


def test_slow_x_does_not_block_telegram_debot_or_market(tmp_path: Path) -> None:
    x = BlockingX()
    telegram = PublicTelegram()
    debot = DeBot()
    market = Market()
    reposts = Reposts()
    stop = Event()
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue:
        service = NarrativeService(
            monitor=x,
            telegram_monitor=telegram,
            debot_feed=debot,
            market_monitor=market,
            x_repost_monitor=reposts,
            queue=queue,
            research_runtime=IdleRuntime(),
            config=NarrativeServiceConfig(
                collector_seconds=0.05, worker_idle_seconds=0.01
            ),
        )
        runner = Thread(target=service.run, args=(stop,))
        runner.start()
        assert x.started.wait(1)
        assert telegram.called.wait(1)
        assert debot.called.wait(1)
        assert market.called.wait(1)
        assert reposts.called.wait(1)
        x.release.set()
        stop.set()
        runner.join(3)
        assert not runner.is_alive()
