"""Tier-aware active X scheduler with bounded first-start replay."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from pathlib import Path
from time import monotonic
from types import MappingProxyType
from typing import Protocol

from ..x import XCheckpoint, XPost, XTimelineBatch, XTimelineClient
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .actors import ActorTier
from .initial_replay import bounded_initial_replay, inside_initial_window
from .monitor_state import JsonXCheckpointStore


DEFAULT_TIER_POLL_SECONDS: Mapping[ActorTier, float] = MappingProxyType({
    ActorTier.GLOBAL_AGENDA: 5.0,
    ActorTier.ECOSYSTEM_AUTHORITY: 5.0,
    ActorTier.ORIGINAL_CREATOR: 5.0,
    ActorTier.DOMAIN_EXPERT: 10.0,
    ActorTier.PROPAGATION_KOL: 15.0,
    ActorTier.UNKNOWN: 15.0,
})


class TimelinePoller(Protocol):
    def poll(
        self, handle: str, checkpoint: XCheckpoint | None = None,
    ) -> XTimelineBatch: ...


class TierPollingPolicy:
    """Validated 5-15 second cadence selected solely from reviewed actor tier."""

    def __init__(self, seconds: Mapping[ActorTier, float] | None = None) -> None:
        values = dict(DEFAULT_TIER_POLL_SECONDS)
        if seconds is not None:
            values.update({ActorTier(key): float(value) for key, value in seconds.items()})
        if set(values) != set(ActorTier):
            raise ValueError("poll policy must cover every actor tier")
        if any(not math.isfinite(value) or not 5 <= value <= 15 for value in values.values()):
            raise ValueError("actor poll intervals must be between 5 and 15 seconds")
        self._seconds = MappingProxyType(values)

    @property
    def seconds(self) -> Mapping[ActorTier, float]:
        return self._seconds

    def interval_for(self, tier: ActorTier, priority: int = 50) -> float:
        base = self._seconds[ActorTier(tier)]
        if not 1 <= priority <= 100:
            raise ValueError("actor priority must be between 1 and 100")
        if priority <= 3:
            return min(base, 5.0)
        if priority <= 5:
            return min(base, 7.5)
        if priority <= 7:
            return min(base, 10.0)
        return base


@dataclass(frozen=True, slots=True)
class MonitorTarget:
    handle: str
    author_id: str
    tier: ActorTier
    priority: int
    interval_seconds: float


@dataclass(frozen=True, slots=True)
class MonitorFailure:
    handle: str
    error_type: str


@dataclass(frozen=True, slots=True)
class _PollAttempt:
    target: MonitorTarget
    previous: XCheckpoint | None
    batch: XTimelineBatch | None = None
    error: Exception | None = None


class NarrativeMonitor:
    """Poll due reviewed actors and return newly published X posts."""

    def __init__(
        self,
        checkpoints: str | Path | JsonXCheckpointStore,
        *,
        client: TimelinePoller | None = None,
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        policy: TierPollingPolicy | None = None,
        clock: Callable[[], float] = monotonic,
        wall_clock: Callable[[], datetime] | None = None,
        max_workers: int = 24,
        initial_replay_limit: int = 1,
        initial_replay_max_age_seconds: float = 300.0,
    ) -> None:
        if isinstance(max_workers, bool) or not 1 <= max_workers <= 64:
            raise ValueError("X monitor workers must be between 1 and 64")
        if isinstance(initial_replay_limit, bool) or not 1 <= initial_replay_limit <= 20:
            raise ValueError("initial replay limit must be between 1 and 20")
        inside_initial_window(
            datetime.now(timezone.utc), datetime.now(timezone.utc),
            max_age_seconds=initial_replay_max_age_seconds,
        )
        self.client = client if client is not None else XTimelineClient()
        self.checkpoints = (
            checkpoints
            if isinstance(checkpoints, JsonXCheckpointStore)
            else JsonXCheckpointStore(checkpoints)
        )
        self.registry = registry
        self.policy = policy if policy is not None else TierPollingPolicy()
        self.clock = clock
        self.wall_clock = wall_clock or (lambda: datetime.now(timezone.utc))
        self.max_workers = max_workers
        self.initial_replay_limit = initial_replay_limit
        self.initial_replay_max_age_seconds = float(initial_replay_max_age_seconds)
        targets: list[MonitorTarget] = []
        for registration in registry.registrations():
            if not registration.author_ids:
                continue
            actor = registration.actor
            if not actor.monitor_x:
                continue
            handle = XCheckpoint(actor.handle).handle
            targets.append(MonitorTarget(
                handle=handle,
                author_id=registration.author_ids[0],
                tier=actor.tier,
                priority=actor.priority,
                interval_seconds=self.policy.interval_for(
                    actor.tier, actor.priority
                ),
            ))
        self.targets = tuple(sorted(
            targets,
            key=lambda item: (
                item.interval_seconds, item.priority, item.handle.casefold()
            ),
        ))
        if not self.targets:
            raise ValueError("narrative monitor requires a stable registered actor")
        self._next_due = {target.handle: float("-inf") for target in self.targets}
        self.last_failures: tuple[MonitorFailure, ...] = ()
        self.last_polled_targets = 0
        self.last_initial_replay_dropped = 0

    def monitor_once(
        self,
        accept: Callable[[tuple[XPost, ...]], None] | None = None,
    ) -> tuple[XPost, ...]:
        """Poll due actors; optionally persist posts before advancing checkpoints."""

        now = self._now()
        due = [target for target in self.targets if self._next_due[target.handle] <= now]
        posts: dict[str, XPost] = {}
        failures: list[MonitorFailure] = []
        initial_replay_dropped = 0
        for target in due:
            self._next_due[target.handle] = now + target.interval_seconds
        attempts = self._poll_due(due)
        self.last_polled_targets = len(attempts)
        for attempt in attempts:
            target = attempt.target
            previous = attempt.previous
            try:
                if attempt.error is not None:
                    raise attempt.error
                if attempt.batch is None:
                    raise RuntimeError("timeline poll returned no batch")
                batch = attempt.batch
                if batch.checkpoint.handle != target.handle:
                    raise ValueError(
                        "timeline client returned a checkpoint for another actor"
                    )
                if batch.checkpoint.user_id != target.author_id:
                    raise ValueError("timeline client returned an untrusted actor identity")
                if previous is None or not previous.latest_tweet_id:
                    observed_at = self._wall_now()
                    fresh, dropped = bounded_initial_replay(
                        batch.posts,
                        limit=self.initial_replay_limit,
                        key=lambda post: int(post.tweet_id),
                        eligible=lambda post: inside_initial_window(
                            post.created_at, observed_at,
                            max_age_seconds=self.initial_replay_max_age_seconds,
                        ),
                    )
                    initial_replay_dropped += dropped
                else:
                    fresh = tuple(
                        post for post in batch.posts
                        if self._strictly_new(post, previous)
                    )
                if fresh and accept is not None:
                    accept(fresh)
                self.checkpoints.save(batch.checkpoint)
            except Exception as exc:
                failures.append(MonitorFailure(target.handle, type(exc).__name__))
                continue
            for post in fresh:
                posts[post.tweet_id] = post
        self.last_failures = tuple(failures)
        self.last_initial_replay_dropped = initial_replay_dropped
        return tuple(sorted(
            posts.values(),
            key=lambda item: (item.created_at, int(item.tweet_id), item.author),
        ))

    def _poll_due(self, due: list[MonitorTarget]) -> tuple[_PollAttempt, ...]:
        if not due:
            return ()
        seeds = tuple(
            (
                target,
                self.checkpoints.load(target.handle),
            )
            for target in due
        )
        attempts: dict[str, _PollAttempt] = {}
        workers = min(self.max_workers, len(seeds))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    self.client.poll,
                    target.handle,
                    previous or XCheckpoint(target.handle, target.author_id),
                ): (target, previous)
                for target, previous in seeds
            }
            for future in as_completed(futures):
                target, previous = futures[future]
                try:
                    attempt = _PollAttempt(target, previous, batch=future.result())
                except Exception as exc:
                    attempt = _PollAttempt(target, previous, error=exc)
                attempts[target.handle] = attempt
        return tuple(attempts[target.handle] for target, _ in seeds)

    def seconds_until_next_poll(self) -> float:
        now = self._now()
        return max(0.0, min(self._next_due.values()) - now)

    def _now(self) -> float:
        value = float(self.clock())
        if not math.isfinite(value):
            raise ValueError("monitor clock must return a finite number")
        return value

    def _wall_now(self) -> datetime:
        value = self.wall_clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("monitor wall clock must be timezone-aware")
        return value.astimezone(timezone.utc)

    @staticmethod
    def _strictly_new(post: XPost, checkpoint: XCheckpoint) -> bool:
        return (
            not checkpoint.latest_tweet_id
            or int(post.tweet_id) > int(checkpoint.latest_tweet_id)
        )
