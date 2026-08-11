from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import stat
from threading import Event, Lock

import pytest

from debot4.v6.narrative.actor_registry import (
    ActorRegistration,
    ActorRegistry,
    DEFAULT_ACTOR_REGISTRY,
)
from debot4.v6.narrative.actors import ActorCapability, ActorRef, ActorTier
from debot4.v6.narrative.monitor import NarrativeMonitor
from debot4.v6.narrative.monitor_state import (
    CHECKPOINT_SCHEMA,
    CheckpointFormatError,
    JsonXCheckpointStore,
)
from debot4.v6.x import XCheckpoint, XPost, XTimelineBatch


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)


class FakeClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value


class FakeTimeline:
    def __init__(self, responses: dict[str, list[tuple[XPost, ...]]] | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, XCheckpoint | None]] = []

    def poll(
        self, handle: str, checkpoint: XCheckpoint | None = None,
    ) -> XTimelineBatch:
        self.calls.append((handle, checkpoint))
        queue = self.responses.get(handle, [])
        posts = queue.pop(0) if queue else ()
        latest = max(
            (checkpoint.latest_tweet_id if checkpoint else "", *(item.tweet_id for item in posts)),
            key=lambda value: int(value or "0"),
        )
        user_id = checkpoint.user_id if checkpoint else _user_id(handle)
        return XTimelineBatch(
            posts=posts,
            checkpoint=XCheckpoint(handle, user_id, latest),
            fetched_items=len(posts),
            request_count=1,
        )


def _user_id(handle: str) -> str:
    handles = sorted(
        item.actor.handle.casefold()
        for item in DEFAULT_ACTOR_REGISTRY.registrations()
    )
    return str(900_000 + handles.index(handle.casefold()))


def _post(handle: str, tweet_id: str, text: str, offset: int) -> XPost:
    created = NOW + timedelta(seconds=offset)
    return XPost(tweet_id, handle, text, created, created)


def _registry(*handles: str) -> ActorRegistry:
    wanted = {item.casefold() for item in handles}
    registrations = tuple(
        item for item in DEFAULT_ACTOR_REGISTRY.registrations()
        if item.actor.handle.casefold() in wanted
    )
    assert len(registrations) == len(wanted)
    return ActorRegistry(registrations)


def test_first_poll_replays_bounded_posts_then_only_new_posts_survive_restart(
    tmp_path: Path,
) -> None:
    old = _post("cz_binance", "2000001", "old baseline", 0)
    middle = _post("cz_binance", "2000002", "middle baseline", 2)
    latest = _post("cz_binance", "2000003", "latest baseline", 4)
    new = _post("cz_binance", "2000004", "new narrative", 5)
    newer = _post("cz_binance", "2000005", "restart narrative", 10)
    timeline = FakeTimeline({
        "cz_binance": [(old, middle, latest), (old, middle, latest, new)]
    })
    clock = FakeClock()
    directory = tmp_path / "private"
    path = directory / "x-checkpoints.json"
    monitor = NarrativeMonitor(
        path, client=timeline, registry=_registry("cz_binance"), clock=clock,
        wall_clock=lambda: NOW + timedelta(seconds=10),
    )

    assert monitor.monitor_once() == (latest,)
    assert monitor.last_initial_replay_dropped == 2
    assert timeline.calls[0][1] is not None
    assert timeline.calls[0][1].user_id == "902926941413453824"
    clock.value = 5.0
    assert monitor.monitor_once() == (new,)
    assert timeline.calls[1][1] == XCheckpoint(
        "cz_binance", "902926941413453824", "2000003"
    )

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == CHECKPOINT_SCHEMA
    assert payload["accounts"]["cz_binance"]["latest_tweet_id"] == "2000004"
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    restarted_timeline = FakeTimeline({"cz_binance": [(new, newer)]})
    restarted = NarrativeMonitor(
        path,
        client=restarted_timeline,
        registry=_registry("cz_binance"),
        clock=FakeClock(),
        wall_clock=lambda: NOW + timedelta(seconds=10),
    )
    assert restarted.monitor_once() == (newer,)
    assert restarted_timeline.calls[0][1] is not None
    assert restarted_timeline.calls[0][1].latest_tweet_id == "2000004"


def test_priority_and_tier_cadence_use_five_ten_fifteen_second_bands(
    tmp_path: Path,
) -> None:
    timeline = FakeTimeline()
    clock = FakeClock()
    monitor = NarrativeMonitor(
        tmp_path / "private" / "x.json",
        client=timeline,
        registry=_registry("elonmusk", "karpathy", "btc2ai", "only1mrwhite"),
        clock=clock,
    )

    assert monitor.monitor_once() == ()
    assert sorted(handle for handle, _ in timeline.calls) == sorted([
        "btc2ai", "elonmusk", "karpathy", "only1mrwhite",
    ])
    timeline.calls.clear()
    clock.value = 4.0
    assert monitor.monitor_once() == ()
    assert timeline.calls == []
    assert monitor.seconds_until_next_poll() == 1.0

    clock.value = 5.0
    monitor.monitor_once()
    assert sorted(handle for handle, _ in timeline.calls) == ["btc2ai", "elonmusk"]
    timeline.calls.clear()
    clock.value = 10.0
    monitor.monitor_once()
    assert sorted(handle for handle, _ in timeline.calls) == sorted([
        "btc2ai", "elonmusk", "karpathy",
    ])
    timeline.calls.clear()
    clock.value = 15.0
    monitor.monitor_once()
    assert sorted(handle for handle, _ in timeline.calls) == sorted([
        "btc2ai", "elonmusk", "only1mrwhite",
    ])


def test_due_accounts_are_polled_concurrently(tmp_path: Path) -> None:
    class BlockingTimeline(FakeTimeline):
        def __init__(self) -> None:
            super().__init__()
            self.started: set[str] = set()
            self.lock = Lock()
            self.ready = Event()

        def poll(
            self, handle: str, checkpoint: XCheckpoint | None = None,
        ) -> XTimelineBatch:
            with self.lock:
                self.started.add(handle)
                if len(self.started) == 2:
                    self.ready.set()
            if not self.ready.wait(1):
                raise RuntimeError("polls ran serially")
            return super().poll(handle, checkpoint)

    timeline = BlockingTimeline()
    monitor = NarrativeMonitor(
        tmp_path / "x.json",
        client=timeline,
        registry=_registry("elonmusk", "cz_binance"),
        clock=FakeClock(),
        max_workers=2,
    )

    assert monitor.monitor_once() == ()
    assert monitor.last_failures == ()
    assert monitor.last_polled_targets == 2
    assert timeline.started == {"elonmusk", "cz_binance"}


def test_checkpoint_store_rejects_documents_outside_its_json_schema(
    tmp_path: Path,
) -> None:
    directory = tmp_path / "private"
    directory.mkdir()
    path = directory / "x.json"
    path.write_text('{"schema":"wrong","accounts":{}}\n', encoding="utf-8")

    with pytest.raises(CheckpointFormatError, match="schema"):
        JsonXCheckpointStore(path)


def test_unverified_targets_are_skipped_and_one_failure_isolated(
    tmp_path: Path,
) -> None:
    class FailingTimeline(FakeTimeline):
        def poll(
            self, handle: str, checkpoint: XCheckpoint | None = None,
        ) -> XTimelineBatch:
            if handle == "elonmusk":
                raise RuntimeError("provider failed")
            return super().poll(handle, checkpoint)

    reviewed = _registry("elonmusk", "cz_binance").registrations()
    pending = ActorRegistration(
        ActorRef(
            "x:four_meme",
            "four_meme",
            ActorTier.ECOSYSTEM_AUTHORITY,
            "numeric identity pending review",
            ("bsc",),
            (ActorCapability.PROPAGATE,),
        ),
        ("https://x.com/four_meme/status/",),
        (),
    )
    monitor = NarrativeMonitor(
        tmp_path / "x.json",
        client=FailingTimeline(),
        registry=ActorRegistry(reviewed + (pending,)),
        clock=FakeClock(),
    )

    assert [item.handle for item in monitor.targets] == ["cz_binance", "elonmusk"]
    assert monitor.monitor_once() == ()
    assert monitor.last_failures[0].handle == "elonmusk"
    assert monitor.last_failures[0].error_type == "RuntimeError"


def test_acceptor_runs_before_checkpoint_and_failure_causes_retry(tmp_path: Path) -> None:
    old = _post("cz_binance", "2000101", "baseline", 0)
    new = _post("cz_binance", "2000102", "new narrative", 5)
    timeline = FakeTimeline({"cz_binance": [(old,), (old, new), (old, new)]})
    clock = FakeClock()
    path = tmp_path / "x.json"
    monitor = NarrativeMonitor(
        path, client=timeline, registry=_registry("cz_binance"), clock=clock,
        wall_clock=lambda: NOW + timedelta(seconds=10),
    )
    monitor.monitor_once()
    clock.value = 5.0

    def fail(_posts: tuple[XPost, ...]) -> None:
        raise OSError("queue unavailable")

    assert monitor.monitor_once(fail) == ()
    assert monitor.last_failures[0].error_type == "OSError"
    assert json.loads(path.read_text())["accounts"]["cz_binance"][
        "latest_tweet_id"
    ] == "2000101"
    clock.value = 10.0
    accepted: list[XPost] = []
    assert monitor.monitor_once(lambda posts: accepted.extend(posts)) == (new,)
    assert accepted == [new]
