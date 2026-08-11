from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from debot4.v6.narrative.actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from debot4.v6.narrative.monitor import NarrativeMonitor
from debot4.v6.narrative.telegram_monitor import TelegramNarrativeMonitor
from debot4.v6.telegram import TelegramChannelBatch, TelegramCheckpoint, TelegramPost
from debot4.v6.x import XCheckpoint, XPost, XTimelineBatch


NOW = datetime(2026, 8, 10, 18, tzinfo=timezone.utc)


def _registration(handle: str):
    return next(
        item for item in DEFAULT_ACTOR_REGISTRY.registrations()
        if item.actor.handle == handle
    )


def test_x_first_start_checkpoints_but_does_not_enqueue_an_old_latest_post(
    tmp_path: Path,
) -> None:
    registration = _registration("cz_binance")
    old = XPost(
        "2000999", "cz_binance", "old post",
        NOW - timedelta(hours=1), NOW,
    )

    class Timeline:
        def poll(self, handle: str, checkpoint=None) -> XTimelineBatch:
            return XTimelineBatch(
                (old,), XCheckpoint(handle, registration.author_ids[0], old.tweet_id),
                1, 1,
            )

    monitor = NarrativeMonitor(
        tmp_path / "x.json", client=Timeline(),
        registry=ActorRegistry((registration,)), clock=lambda: 0,
        wall_clock=lambda: NOW,
    )

    assert monitor.monitor_once() == ()
    assert monitor.last_initial_replay_dropped == 1
    assert monitor.checkpoints.load("cz_binance").latest_tweet_id == old.tweet_id


def test_telegram_first_start_checkpoints_but_does_not_enqueue_old_message(
    tmp_path: Path,
) -> None:
    registration = _registration("yeonwoo1102")
    old = TelegramPost(
        "yndegen", 99, "old message", NOW - timedelta(hours=1), NOW,
    )

    class Telegram:
        def poll(self, channel: str, checkpoint=None) -> TelegramChannelBatch:
            return TelegramChannelBatch(
                (old,), TelegramCheckpoint(channel, old.message_id), 1,
            )

    monitor = TelegramNarrativeMonitor(
        tmp_path / "telegram.json", client=Telegram(),
        registry=ActorRegistry((registration,)), clock=lambda: 0,
        wall_clock=lambda: NOW,
    )

    assert monitor.monitor_once() == ()
    assert monitor.last_initial_replay_dropped == 1
    assert monitor.checkpoints.load("yndegen").latest_message_id == old.message_id
