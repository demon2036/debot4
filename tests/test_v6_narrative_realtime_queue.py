from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from debot4.v6.narrative.actor_registry import DEFAULT_ACTOR_REGISTRY
from debot4.v6.narrative.job_priority import (
    REPLAY_PRIORITY,
    narrative_job_priority,
)
from debot4.v6.narrative.job_queue import NarrativeJobQueue
from debot4.v6.x.models import XPost


NOW = datetime(2026, 8, 10, 18, tzinfo=timezone.utc)


@dataclass
class Clock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def _post(tweet_id: str, created_at: datetime) -> XPost:
    return XPost(
        tweet_id,
        "cz_binance",
        f"narrative {tweet_id}",
        created_at,
        created_at,
    )


def test_priority_demotes_historical_replay_but_keeps_live_actor_weight() -> None:
    actor_priority = DEFAULT_ACTOR_REGISTRY.resolve("cz_binance").priority
    live = _post("2000000000000000001", NOW - timedelta(seconds=20))
    replay = _post("2000000000000000002", NOW - timedelta(minutes=20))

    assert narrative_job_priority(live, now=NOW) == actor_priority
    assert narrative_job_priority(replay, now=NOW) == REPLAY_PRIORITY


def test_startup_reprioritization_moves_live_work_ahead_of_old_backlog(
    tmp_path,
) -> None:
    clock = Clock()
    replay = _post("2000000000000000001", NOW - timedelta(hours=1))
    live = _post("2000000000000000002", NOW - timedelta(seconds=10))
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3", clock=clock) as queue:
        replay_id = queue.enqueue(replay, priority=1)
        live_id = queue.enqueue(live, priority=50)
        changed = queue.reprioritize_pending(
            lambda payload: narrative_job_priority(payload, now=clock())
        )

        assert changed == 2
        assert queue.get(replay_id).priority == REPLAY_PRIORITY
        assert queue.claim("worker").job_id == live_id


def test_equal_priority_claims_newest_collected_job_first(tmp_path) -> None:
    clock = Clock()
    first = _post("2000000000000000001", NOW)
    second = _post("2000000000000000002", NOW)
    with NarrativeJobQueue(tmp_path / "jobs.sqlite3", clock=clock) as queue:
        queue.enqueue(first, priority=50)
        clock.advance(1)
        second_id = queue.enqueue(second, priority=50)

        assert queue.claim("worker").job_id == second_id
