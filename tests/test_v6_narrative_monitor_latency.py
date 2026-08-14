from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Lock, Thread

from debot4.v6.narrative.actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from debot4.v6.narrative.monitor import NarrativeMonitor
from debot4.v6.x.models import XCheckpoint, XPost, XTimelineBatch


NOW = datetime(2026, 8, 13, 13, 30, 41, tzinfo=timezone.utc)


def _registry() -> ActorRegistry:
    wanted = {"flapdotsh", "cz_binance"}
    return ActorRegistry(tuple(
        item for item in DEFAULT_ACTOR_REGISTRY.registrations()
        if item.actor.handle.casefold() in wanted
    ))


class _OneFastOneBlockedTimeline:
    def __init__(self) -> None:
        self.started: set[str] = set()
        self.lock = Lock()
        self.both_started = Event()
        self.release_slow = Event()

    def poll(
        self, handle: str, checkpoint: XCheckpoint | None = None,
    ) -> XTimelineBatch:
        assert checkpoint is not None
        with self.lock:
            self.started.add(handle)
            if len(self.started) == 2:
                self.both_started.set()
        assert self.both_started.wait(2)
        if handle == "cz_binance":
            assert self.release_slow.wait(2)
            posts: tuple[XPost, ...] = ()
            latest = ""
        else:
            post = XPost(
                "2087894611733922300",
                "flapdotsh",
                "Introducing the Flap bBroker Vault on BNB Chain.",
                NOW,
                NOW + timedelta(seconds=5),
            )
            posts = (post,)
            latest = post.tweet_id
        return XTimelineBatch(
            posts,
            XCheckpoint(handle, checkpoint.user_id, latest),
            len(posts),
            1,
        )


def test_fast_catalyst_is_accepted_before_another_x_target_finishes(
    tmp_path: Path,
) -> None:
    timeline = _OneFastOneBlockedTimeline()
    monitor = NarrativeMonitor(
        tmp_path / "x.json",
        client=timeline,
        registry=_registry(),
        wall_clock=lambda: NOW + timedelta(seconds=6),
        max_workers=2,
    )
    accepted = Event()
    observed: list[XPost] = []

    def accept(posts: tuple[XPost, ...]) -> None:
        observed.extend(posts)
        accepted.set()

    runner = Thread(target=monitor.monitor_once, kwargs={"accept": accept})
    runner.start()
    assert accepted.wait(1), "fast Flap post waited for the slow X request"
    assert [item.tweet_id for item in observed] == ["2087894611733922300"]
    assert runner.is_alive()
    timeline.release_slow.set()
    runner.join(2)
    assert not runner.is_alive()
