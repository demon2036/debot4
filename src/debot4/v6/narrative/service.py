"""Concurrent collection and research loops for the narrative system."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from threading import Event, Lock, Thread
from time import monotonic

from ..identity import utc_datetime, utc_now
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .collection import CollectionCycle, NarrativeCollector
from .collection_sources import (
    ChainMintSource,
    DeBotSource,
    MarketSource,
    MintSource,
    RepostSource,
    TelegramSource,
    TelegramRealtimeSource,
    XSource,
)
from .job_queue import NarrativeJobQueue
from .job_priority import narrative_job_priority
from .live_signal_filter import NarrativeSignalFilter
from .catalyst_mint_state import CatalystMintState
from .mint_location_store import MintLocationStore
from .service_config import NarrativeServiceConfig
from .worker import NarrativeResearchWorker, ResearchRuntime, WorkCycle


THREAD_JOIN_SECONDS = 12.0


class NarrativeService:
    """Run fast collectors independently from the slower Grok worker."""

    def __init__(
        self,
        *,
        monitor: XSource,
        telegram_monitor: TelegramSource,
        debot_feed: DeBotSource,
        market_monitor: MarketSource | None = None,
        mint_monitor: MintSource | None = None,
        catalyst_mints: CatalystMintState | None = None,
        chain_mint_monitor: ChainMintSource | None = None,
        mint_locations: MintLocationStore | None = None,
        queue: NarrativeJobQueue,
        research_runtime: ResearchRuntime,
        telegram_realtime: TelegramRealtimeSource | None = None,
        x_repost_monitor: RepostSource | None = None,
        config: NarrativeServiceConfig | None = None,
        worker: str = "narrative-grok-1",
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        clock: Callable[[], datetime] = utc_now,
        signal_filter: NarrativeSignalFilter | None = None,
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
            mint_monitor=mint_monitor,
            catalyst_mints=catalyst_mints,
            chain_mint_monitor=chain_mint_monitor,
            mint_locations=mint_locations,
            max_attempts=self.config.max_attempts,
            registry=registry,
            clock=clock,
            signal_filter=signal_filter,
        )
        worker_base = worker.removesuffix("-1")
        self.workers = tuple(
            NarrativeResearchWorker(
                queue,
                research_runtime,
                worker=f"{worker_base}-{index}",
                lease_seconds=self.config.lease_seconds,
                retry_delay_seconds=self.config.retry_delay_seconds,
            )
            for index in range(1, self.config.research_workers + 1)
        )
        self.worker = self.workers[0]
        self.telegram_realtime = telegram_realtime
        self.x_repost_monitor = x_repost_monitor
        self._error_lock = Lock()
        self.last_source_error_types: dict[str, str | None] = {
            "x": None,
            "telegram_public": None,
            "debot": None,
            **({"x_reposts": None} if x_repost_monitor is not None else {}),
            **({"market": None} if market_monitor is not None else {}),
            **({"debot_new_mints": None} if mint_monitor is not None else {}),
            **({"bsc_factory_mints": None} if chain_mint_monitor is not None else {}),
        }
        self.last_collector_error_type: str | None = None
        self.last_worker_error_type: str | None = None
        self.last_worker_error_types: dict[str, str | None] = {
            item.worker: None for item in self.workers
        }
        self.last_realtime_error_type: str | None = None

    def run_source(
        self,
        stop: Event,
        source: str,
        collect: Callable[[], object],
        wait_seconds: float | None = None,
    ) -> None:
        interval = self.config.collector_seconds if wait_seconds is None else wait_seconds
        while not stop.is_set():
            started = monotonic()
            try:
                collect()
                self._set_source_error(source, None)
            except Exception as exc:
                self._set_source_error(source, type(exc).__name__)
            stop.wait(max(0.0, interval - (monotonic() - started)))

    def run_worker(
        self,
        stop: Event,
        worker: NarrativeResearchWorker | None = None,
    ) -> None:
        selected = worker or self.worker
        while not stop.is_set():
            try:
                cycle = selected.work_once()
                self._set_worker_error(selected.worker, None)
            except Exception as exc:
                self._set_worker_error(selected.worker, type(exc).__name__)
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
        cadence = self.config.collector_seconds
        sources: list[tuple[str, Callable[[], object], float]] = [
            ("x", self.collector.collect_x_once, cadence),
            ("telegram_public", self.collector.collect_telegram_once, cadence),
            ("debot", self.collector.collect_debot_once, cadence),
        ]
        if self.collector.market_monitor is not None:
            sources.append(("market", self.collector.collect_market_once, cadence))
        if self.collector.mint_monitor is not None:
            sources.append(("debot_new_mints", self.collector.collect_mints_once, cadence))
        if self.collector.chain_mint_monitor is not None:
            sources.append((
                "bsc_factory_mints", self.collector.collect_chain_mints_once,
                min(cadence, self.collector.chain_mint_monitor.poll_seconds),
            ))
        if self.x_repost_monitor is not None:
            sources.append(("x_reposts", self.x_repost_monitor.poll_once, cadence))
        threads = [
            Thread(
                target=self.run_source,
                args=(stop, name, collect, wait_seconds),
                name=f"narrative-{name}",
                daemon=True,
            )
            for name, collect, wait_seconds in sources
        ]
        threads.extend(
            Thread(
                target=self.run_worker,
                args=(stop, worker),
                name=worker.worker,
                daemon=True,
            )
            for worker in self.workers
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

    def _set_worker_error(self, worker: str, error_type: str | None) -> None:
        with self._error_lock:
            self.last_worker_error_types[worker] = error_type
            self.last_worker_error_type = next(
                (
                    item for item in self.last_worker_error_types.values()
                    if item is not None
                ),
                None,
            )
__all__ = [
    "CollectionCycle",
    "NarrativeCollector",
    "NarrativeResearchWorker",
    "NarrativeService",
    "NarrativeServiceConfig",
    "WorkCycle",
]
