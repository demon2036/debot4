"""Fast, durable collection for every narrative discovery source."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from threading import Lock
from typing import Protocol

from ..domain import DeBotSignal
from ..identity import utc_now
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .debot_feed import NarrativeDeBotCandidate
from .job_priority import narrative_job_priority
from .job_queue import NarrativeJobQueue
from .live_signal_filter import (
    AllowAllSignalFilter,
    NarrativeSignal,
    NarrativeSignalFilter,
    SignalFilterDecision,
)
from .market_signal import MarketAnomaly


class XSource(Protocol):
    def monitor_once(
        self, accept: Callable[[tuple[XPost, ...]], None] | None = None,
    ) -> tuple[XPost, ...]: ...


class TelegramSource(Protocol):
    def monitor_once(
        self, accept: Callable[[tuple[TelegramPost, ...]], None] | None = None,
    ) -> tuple[TelegramPost, ...]: ...


class DeBotSource(Protocol):
    def poll_once(
        self,
        *,
        anomaly: str | None = None,
        accept: Callable[[tuple[NarrativeDeBotCandidate, ...]], object] | None = None,
    ) -> tuple[NarrativeDeBotCandidate, ...]: ...


class MarketSource(Protocol):
    def poll_once(
        self,
        accept: Callable[[tuple[MarketAnomaly, ...]], object] | None = None,
    ) -> tuple[MarketAnomaly, ...]: ...


@dataclass(frozen=True, slots=True)
class CollectionCycle:
    x_posts: int
    telegram_posts: int
    debot_signals: int
    market_anomalies: int = 0

    @property
    def active_posts(self) -> int:
        return self.x_posts

    @property
    def passive_signals(self) -> int:
        return self.debot_signals + self.market_anomalies


class NarrativeCollector:
    """Persist source items before their source checkpoint is advanced."""

    def __init__(
        self,
        monitor: XSource,
        telegram_monitor: TelegramSource,
        debot_feed: DeBotSource,
        queue: NarrativeJobQueue,
        *,
        market_monitor: MarketSource | None = None,
        max_attempts: int = 3,
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        clock: Callable[[], datetime] = utc_now,
        signal_filter: NarrativeSignalFilter | None = None,
    ) -> None:
        if isinstance(max_attempts, bool) or not 1 <= max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        self.monitor = monitor
        self.telegram_monitor = telegram_monitor
        self.debot_feed = debot_feed
        self.market_monitor = market_monitor
        self.queue = queue
        self.max_attempts = max_attempts
        self.registry = registry
        self.clock = clock
        self.signal_filter = signal_filter or AllowAllSignalFilter()
        self._filter_counts: Counter[tuple[bool, str]] = Counter()
        self._filter_lock = Lock()

    def collect_once(self) -> CollectionCycle:
        x_posts = self.collect_x_once()
        telegram_posts = self.collect_telegram_once()
        candidates = self.collect_debot_once()
        anomalies = self.collect_market_once()
        return CollectionCycle(
            len(x_posts), len(telegram_posts), len(candidates), len(anomalies)
        )

    def collect_x_once(self) -> tuple[XPost, ...]:
        return self.monitor.monitor_once(accept=self._accept_x)

    def collect_telegram_once(self) -> tuple[TelegramPost, ...]:
        return self.telegram_monitor.monitor_once(accept=self.accept_telegram)

    def collect_debot_once(self) -> tuple[NarrativeDeBotCandidate, ...]:
        return self.debot_feed.poll_once(accept=self._accept_debot)

    def collect_market_once(self) -> tuple[MarketAnomaly, ...]:
        if self.market_monitor is None:
            return ()
        return self.market_monitor.poll_once(accept=self._accept_market)

    def filter_snapshot(self) -> dict[str, object]:
        with self._filter_lock:
            counts = dict(self._filter_counts)
        accepted = sum(total for (keep, _), total in counts.items() if keep)
        rejected = sum(total for (keep, _), total in counts.items() if not keep)
        return {
            "accepted": accepted,
            "rejected": rejected,
            "reasons": {
                reason: total
                for (_, reason), total in sorted(
                    counts.items(), key=lambda item: item[0]
                )
            },
        }

    def _enqueue(self, payload: NarrativeSignal) -> None:
        decision = self.signal_filter.decide(payload)
        if not decision.accepted:
            self._record_filter(decision)
            return
        self.queue.enqueue(
            payload,
            max_attempts=self.max_attempts,
            priority=narrative_job_priority(
                payload, self.registry, now=self.clock()
            ),
        )
        self._record_filter(decision)

    def _record_filter(self, decision: SignalFilterDecision) -> None:
        with self._filter_lock:
            self._filter_counts[(decision.accepted, decision.reason)] += 1

    def _accept_x(self, posts: tuple[XPost, ...]) -> None:
        for post in posts:
            self._enqueue(post)

    def accept_telegram(self, posts: tuple[TelegramPost, ...]) -> None:
        """Persist realtime or public Telegram observations idempotently."""

        for post in posts:
            self._enqueue(post)

    def _accept_debot(
        self, candidates: tuple[NarrativeDeBotCandidate, ...]
    ) -> None:
        for candidate in candidates:
            self._enqueue(candidate.signal)

    def _accept_market(self, anomalies: tuple[MarketAnomaly, ...]) -> None:
        for anomaly in anomalies:
            self._enqueue(anomaly)
