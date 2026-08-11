from __future__ import annotations

import asyncio
from types import SimpleNamespace

from debot4.v6.telegram.membership import resolve_joined_channels


class FakeClient:
    async def get_entity(self, channel: str) -> object:
        if channel == "missing":
            raise ValueError("not found")
        return SimpleNamespace(
            id={"joined": 1, "unjoined": 2}[channel],
            left=channel == "unjoined",
        )


def test_only_joined_channels_are_eligible_for_realtime_updates() -> None:
    result = asyncio.run(resolve_joined_channels(
        FakeClient(), ("joined", "unjoined", "missing"),
    ))

    assert tuple(item.id for item in result.entities) == (1,)
    assert result.by_id == {1: "joined"}
    assert result.unjoined == 1
    assert result.unresolved == 1
    assert result.error_type == "TelegramChannelReadinessError"


def test_subscription_failure_is_distinct_from_resolution_failure() -> None:
    result = asyncio.run(resolve_joined_channels(
        FakeClient(), ("unjoined",),
    ))

    assert result.entities == ()
    assert result.error_type == "TelegramChannelSubscriptionError"
