"""Tier-aware scheduler for reviewed public Telegram channels."""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from time import monotonic
from typing import Protocol

from ..telegram import (
    JsonTelegramCheckpointStore, TelegramChannelBatch, TelegramCheckpoint,
    TelegramPost, TelegramPublicClient,
)
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .actors import ActorTier
from .initial_replay import bounded_initial_replay, inside_initial_window
from .monitor import TierPollingPolicy


class TelegramPoller(Protocol):
    def poll(
        self, channel: str, checkpoint: TelegramCheckpoint | None = None,
    ) -> TelegramChannelBatch: ...


@dataclass(frozen=True, slots=True)
class TelegramMonitorTarget:
    channel: str
    actor_handle: str
    tier: ActorTier
    priority: int
    interval_seconds: float


@dataclass(frozen=True, slots=True)
class TelegramMonitorFailure:
    channel: str
    error_type: str


@dataclass(frozen=True, slots=True)
class _PollAttempt:
    target: TelegramMonitorTarget
    previous: TelegramCheckpoint | None
    batch: TelegramChannelBatch | None = None
    error: Exception | None = None


class TelegramNarrativeMonitor:
    """Poll public channels; persist accepted messages before checkpoints."""

    def __init__(
        self,
        checkpoints: str | Path | JsonTelegramCheckpointStore,
        *,
        client: TelegramPoller | None = None,
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        policy: TierPollingPolicy | None = None,
        clock: Callable[[], float] = monotonic,
        wall_clock: Callable[[], datetime] | None = None,
        max_workers: int = 12,
        initial_replay_limit: int = 1,
        initial_replay_max_age_seconds: float = 300.0,
    ) -> None:
        if isinstance(max_workers, bool) or not 1 <= max_workers <= 32:
            raise ValueError("Telegram monitor workers must be between 1 and 32")
        if isinstance(initial_replay_limit, bool) or not 1 <= initial_replay_limit <= 20:
            raise ValueError("initial replay limit must be between 1 and 20")
        inside_initial_window(
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            max_age_seconds=initial_replay_max_age_seconds,
        )
        self.client = client if client is not None else TelegramPublicClient()
        self.checkpoints = (
            checkpoints
            if isinstance(checkpoints, JsonTelegramCheckpointStore)
            else JsonTelegramCheckpointStore(checkpoints)
        )
        self.registry = registry
        self.policy = policy if policy is not None else TierPollingPolicy()
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.max_workers = max_workers
        self.initial_replay_limit = initial_replay_limit
        self.initial_replay_max_age_seconds = float(initial_replay_max_age_seconds)
        targets = [
            TelegramMonitorTarget(
                channel=channel.casefold(),
                actor_handle=registration.actor.handle,
                tier=registration.actor.tier,
                priority=registration.actor.priority,
                interval_seconds=self.policy.interval_for(
                    registration.actor.tier, registration.actor.priority
                ),
            )
            for registration in registry.registrations()
            for channel in registration.actor.telegram_public_channels
        ]
        self.targets = tuple(sorted(
            targets,
            key=lambda item: (
                item.interval_seconds, item.priority, item.channel,
            ),
        ))
        if not self.targets:
            raise ValueError("Telegram monitor requires a reviewed public channel")
        self._next_due = {target.channel: float("-inf") for target in self.targets}
        self.last_failures: tuple[TelegramMonitorFailure, ...] = ()
        self.last_polled_targets = 0
        self.last_initial_replay_dropped = 0

    def monitor_once(
        self,
        accept: Callable[[tuple[TelegramPost, ...]], None] | None = None,
    ) -> tuple[TelegramPost, ...]:
        now = self._now()
        due = [target for target in self.targets if self._next_due[target.channel] <= now]
        for target in due:
            self._next_due[target.channel] = now + target.interval_seconds
        posts: dict[str, TelegramPost] = {}
        failures: list[TelegramMonitorFailure] = []
        initial_replay_dropped = 0
        attempts = self._poll_due(due)
        self.last_polled_targets = len(attempts)
        for attempt in attempts:
            try:
                if attempt.error is not None:
                    raise attempt.error
                if attempt.batch is None:
                    raise RuntimeError("Telegram poll returned no batch")
                batch = attempt.batch
                if batch.checkpoint.channel != attempt.target.channel:
                    raise ValueError("Telegram poll crossed channel boundary")
                if attempt.previous is None:
                    observed_at = self._wall_now()
                    fresh, dropped = bounded_initial_replay(
                        batch.posts,
                        limit=self.initial_replay_limit,
                        key=lambda item: item.message_id,
                        eligible=lambda item: inside_initial_window(
                            item.created_at, observed_at,
                            max_age_seconds=self.initial_replay_max_age_seconds,
                        ),
                    )
                    initial_replay_dropped += dropped
                else:
                    previous_id = attempt.previous.latest_message_id
                    fresh = tuple(
                        item for item in batch.posts if item.message_id > previous_id
                    )
                if fresh and accept is not None:
                    accept(fresh)
                self.checkpoints.save(batch.checkpoint)
            except Exception as exc:
                failures.append(TelegramMonitorFailure(
                    attempt.target.channel, type(exc).__name__
                ))
                continue
            for post in fresh:
                posts[post.source_id] = post
        self.last_failures = tuple(failures)
        self.last_initial_replay_dropped = initial_replay_dropped
        return tuple(sorted(
            posts.values(),
            key=lambda item: (item.created_at, item.channel, item.message_id),
        ))

    def _poll_due(self, due: list[TelegramMonitorTarget]) -> tuple[_PollAttempt, ...]:
        if not due:
            return ()
        seeds = tuple(
            (target, self.checkpoints.load(target.channel)) for target in due
        )
        attempts: dict[str, _PollAttempt] = {}
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(seeds))) as pool:
            futures = {
                pool.submit(self.client.poll, target.channel, previous): (
                    target, previous
                )
                for target, previous in seeds
            }
            for future in as_completed(futures):
                target, previous = futures[future]
                try:
                    attempt = _PollAttempt(target, previous, future.result())
                except Exception as exc:
                    attempt = _PollAttempt(target, previous, error=exc)
                attempts[target.channel] = attempt
        return tuple(attempts[target.channel] for target, _ in seeds)

    def seconds_until_next_poll(self) -> float:
        now = self._now()
        return max(0.0, min(self._next_due.values()) - now)

    def _now(self) -> float:
        value = float(self.clock())
        if not math.isfinite(value):
            raise ValueError("Telegram monitor clock must be finite")
        return value

    def _wall_now(self) -> datetime:
        value = self.wall_clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Telegram monitor wall clock must be timezone-aware")
        return value.astimezone(timezone.utc)
