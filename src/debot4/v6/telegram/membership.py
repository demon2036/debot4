"""Resolve only Telegram channels the authenticated account has joined."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TelegramChannelResolution:
    entities: tuple[Any, ...]
    by_id: dict[int, str]
    unresolved: int
    unjoined: int

    @property
    def error_type(self) -> str | None:
        if self.unresolved and self.unjoined:
            return "TelegramChannelReadinessError"
        if self.unjoined:
            return "TelegramChannelSubscriptionError"
        if self.unresolved:
            return "TelegramChannelResolutionError"
        return None


async def resolve_joined_channels(
    client: Any, channels: tuple[str, ...],
) -> TelegramChannelResolution:
    entities: list[Any] = []
    by_id: dict[int, str] = {}
    unresolved = 0
    unjoined = 0
    for channel in channels:
        try:
            entity = await client.get_entity(channel)
            entity_id = int(getattr(entity, "id"))
        except Exception:
            unresolved += 1
            continue
        if getattr(entity, "left", False) is True:
            unjoined += 1
            continue
        entities.append(entity)
        by_id[entity_id] = channel
    return TelegramChannelResolution(
        tuple(entities), by_id, unresolved, unjoined,
    )


__all__ = ["TelegramChannelResolution", "resolve_joined_channels"]
