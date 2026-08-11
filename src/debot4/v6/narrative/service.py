"""Concurrent collection and research loops for the narrative system."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import math
from threading import Event, Lock, Thread
from typing import Protocol

from ..identity import utc_datetime, utc_now
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .collection import (
    CollectionCycle,
    DeBotSource,
    MarketSource,
    NarrativeCollector,
    TelegramSource,
    XSource,
)
from .job_queue import NarrativeJobQueue
from .job_priority import narrative_job_priority
from .worker import NarrativeResearchWorker, ResearchRuntime, WorkCycle


MIN_COLLECTOR_SECONDS = 0.05
MAX_COLLECTOR_SECONDS = 2.0
THREAD_JOIN_SECONDS = 12.0


class TelegramRealtimeSource(Protocol):
    def run(
        self,
        stop: Event,
        accept: Callable[[tuple[object, ...]], None],
    ) -> None: ...


class RepostSource(Protocol):
    def poll_once(self) -> tuple[object, ...]: ...


@dataclass(frozen=True, slots=True)
class NarrativeServiceConfig:
    """Bounded timings: scheduling is fast and never uses a 30-second tick."""

    collector_seconds: float = 0.25
    worker_idle_seconds: float = 0.25
    lease_seconds: float = 120.0
    retry_delay_seconds: float = 1.0
    max_attempts: int = 3

    def __post_init__(self) -> None:
        _seconds(
            "collector_seconds",
            self.collector_seconds,
            MIN_COLLECTOR_SECONDS,
            MAX_COLLECTOR_SECONDS,
        )
        _seconds("worker_idle_seconds", self.worker_idle_seconds, 0.01, 2.0)
        _seconds("lease_seconds", self.lease_seconds, 0.01, 86_400.0)
        _seconds("retry_delay_seconds", self.retry_delay_seconds, 0.0, 86_400.0)
        if isinstance(self.max_attempts, bool) or not 1 <= self.max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")


class NarrativeService:
    """Run fast collectors independently from the slower Grok worker."""

    def __init__(
        self,
        *,
        monitor: XSource,
        telegram_monitor: TelegramSource,
        debot_feed: DeBotSource,
        market_monitor: MarketSource | None = None,
        queue: NarrativeJobQueue,
        research_runtime: ResearchRuntime,
        telegram_realtime: TelegramRealtimeSource | None = None,
        x_repost_monitor: RepostSource | None = None,
        config: NarrativeServiceConfig | None = None,
        worker: str = "narrative-grok-1",
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.config = config or NarrativeServiceConfig()
        priority_at = utc_datetime(clock())
        queue.reprioritize_pending(
            lambda payload: narrative_job_priority(
                payload, registry, now=priority_at
            )
        )
        self.collector = NarrativeCollector(
            monitor,
            telegram_monitor,
            debot_feed,
            queue,
            market_monitor=market_monitor,
            max_attempts=self.config.max_attempts,
            registry=registry,
            clock=clock,
        )
        self.worker = NarrativeResearchWorker(
            queue,
            research_runtime,
            worker=worker,
            lease_seconds=self.config.lease_seconds,
            retry_delay_seconds=self.config.retry_delay_seconds,
        )
        self.telegram_realtime = telegram_realtime
        self.x_repost_monitor = x_repost_monitor
        self._error_lock = Lock()
        self.last_source_error_types: dict[str, str | None] = {
            "x": None,
            "telegram_public": None,
            "debot": None,
            **({"x_reposts": None} if x_repost_monitor is not None else {}),
            **({"market": None} if market_monitor is not None else {}),
        }
        self.last_collector_error_type: str | None = None
        self.last_worker_error_type: str | None = None
        self.last_realtime_error_type: str | None = None

    def run_source(
        self,
        stop: Event,
        source: str,
        collect: Callable[[], object],
    ) -> None:
        while not stop.is_set():
            try:
                collect()
                self._set_source_error(source, None)
            except Exception as exc:
                self._set_source_error(source, type(exc).__name__)
            stop.wait(self.config.collector_seconds)

    def run_worker(self, stop: Event) -> None:
        while not stop.is_set():
            try:
                cycle = self.worker.work_once()
                self.last_worker_error_type = None
            except Exception as exc:
                self.last_worker_error_type = type(exc).__name__
                stop.wait(self.config.worker_idle_seconds)
                continue
            if cycle.idle:
                stop.wait(self.config.worker_idle_seconds)

    def run_realtime(self, stop: Event) -> None:
        if self.telegram_realtime is None:
            return
        try:
            self.telegram_realtime.run(stop, self.collector.accept_telegram)
            self.last_realtime_error_type = None
        except Exception as exc:
            self.last_realtime_error_type = type(exc).__name__

    def run(self, stop: Event) -> None:
        if stop.is_set():
            return
        sources: list[tuple[str, Callable[[], object]]] = [
            ("x", self.collector.collect_x_once),
            ("telegram_public", self.collector.collect_telegram_once),
            ("debot", self.collector.collect_debot_once),
        ]
        if self.collector.market_monitor is not None:
            sources.append(("market", self.collector.collect_market_once))
        if self.x_repost_monitor is not None:
            sources.append(("x_reposts", self.x_repost_monitor.poll_once))
        threads = [
            Thread(
                target=self.run_source,
                args=(stop, name, collect),
                name=f"narrative-{name}",
                daemon=True,
            )
            for name, collect in sources
        ]
        threads.append(
            Thread(
                target=self.run_worker,
                args=(stop,),
                name="narrative-grok-worker",
                daemon=True,
            )
        )
        if self.telegram_realtime is not None:
            threads.append(Thread(
                target=self.run_realtime,
                args=(stop,),
                name="narrative-telegram-realtime",
                daemon=True,
            ))
        for thread in threads:
            thread.start()
        try:
            while not stop.wait(0.25):
                if not all(thread.is_alive() for thread in threads):
                    break
        finally:
            stop.set()
            for thread in threads:
                thread.join(THREAD_JOIN_SECONDS)

    def _set_source_error(self, source: str, error_type: str | None) -> None:
        with self._error_lock:
            self.last_source_error_types[source] = error_type
            self.last_collector_error_type = next(
                (
                    item for item in self.last_source_error_types.values()
                    if item is not None
                ),
                None,
            )


def _seconds(name: str, value: float, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= float(value) <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")


__all__ = [
    "CollectionCycle",
    "NarrativeCollector",
    "NarrativeResearchWorker",
    "NarrativeService",
    "NarrativeServiceConfig",
    "WorkCycle",
]
