"""Read-only Telegram user-session event adapter with bounded retries."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
import inspect
from threading import Event, RLock
from typing import Any

from ..identity import utc_datetime, utc_now
from .membership import resolve_joined_channels
from .models import TelegramPost, telegram_channel
from .realtime_event import event_post
from .realtime_config import TelegramRealtimeConfig


class TelegramRealtimeUnavailable(RuntimeError):
    """The authenticated read-only update stream cannot currently run."""


@dataclass(frozen=True, slots=True)
class TelegramRealtimeHealth:
    status: str
    configured_channels: int
    watched_channels: int
    events_received: int
    last_event_at: datetime | None = None
    last_error_type: str | None = None

    def as_public_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "configured_channels": self.configured_channels,
            "watched_channels": self.watched_channels,
            "events_received": self.events_received,
            "last_event_at": (
                None if self.last_event_at is None else self.last_event_at.isoformat()
            ),
            "last_error_type": self.last_error_type,
        }


class TelegramRealtimeMonitor:
    """Subscribe to reviewed channels without sending or forwarding messages."""

    def __init__(
        self,
        config: TelegramRealtimeConfig,
        channels: Sequence[str],
        *,
        retry_seconds: float = 2.0,
        clock: Callable[[], datetime] = utc_now,
        client_factory: Callable[[TelegramRealtimeConfig], Any] | None = None,
        event_filter_factory: Callable[[Sequence[Any]], Any] | None = None,
    ) -> None:
        normalized = tuple(dict.fromkeys(telegram_channel(item) for item in channels))
        if not normalized:
            raise ValueError("Telegram realtime monitor requires reviewed channels")
        if isinstance(retry_seconds, bool) or not 0.05 <= retry_seconds <= 60:
            raise ValueError("Telegram retry interval must be between 0.05 and 60 seconds")
        self.config = config
        self.channels = normalized
        self.retry_seconds = float(retry_seconds)
        self.clock = clock
        self._client_factory = client_factory or _telethon_client
        self._event_filter_factory = event_filter_factory or _new_message_filter
        self._lock = RLock()
        self._health = TelegramRealtimeHealth("stopped", len(normalized), 0, 0)

    def snapshot(self) -> TelegramRealtimeHealth:
        with self._lock:
            return self._health

    def run(
        self,
        stop: Event,
        accept: Callable[[tuple[TelegramPost, ...]], None],
    ) -> None:
        self._set(status="starting", watched=0, error=None)
        while not stop.is_set():
            try:
                asyncio.run(self._connected_run(stop, accept))
            except Exception as exc:
                self._set(status="degraded", watched=0, error=type(exc).__name__)
                if stop.wait(self.retry_seconds):
                    break
            else:
                if not stop.is_set():
                    self._set(
                        status="degraded", watched=0,
                        error="TelegramRealtimeDisconnected",
                    )
                    if stop.wait(self.retry_seconds):
                        break
        current = self.snapshot()
        self._set(
            status="stopped", watched=0, error=current.last_error_type,
        )

    async def _connected_run(
        self,
        stop: Event,
        accept: Callable[[tuple[TelegramPost, ...]], None],
    ) -> None:
        client = self._client_factory(self.config)
        try:
            await client.connect()
            if not await client.is_user_authorized():
                raise TelegramRealtimeUnavailable("Telegram session is unauthorized")
            resolution = await resolve_joined_channels(client, self.channels)
            entities = resolution.entities
            if not entities:
                reason = (
                    "reviewed Telegram channels are not joined"
                    if resolution.unjoined
                    else "no reviewed Telegram channel resolved"
                )
                raise TelegramRealtimeUnavailable(reason)

            async def on_message(event: Any) -> None:
                try:
                    post = event_post(
                        event, resolution.by_id, self.channels, self.clock(),
                    )
                    if post is None:
                        return
                    await _deliver(accept, post)
                    self._record_event(self.clock())
                except Exception as exc:
                    self._set(
                        status="degraded", watched=len(entities),
                        error=type(exc).__name__,
                    )

            event_filter = self._event_filter_factory(entities)
            client.add_event_handler(on_message, event_filter)
            self._set(
                status="degraded" if resolution.error_type else "live",
                watched=len(entities),
                error=resolution.error_type,
            )
            stopper = asyncio.create_task(_disconnect_on_stop(client, stop))
            try:
                try:
                    await client.run_until_disconnected()
                except asyncio.CancelledError:
                    if not stop.is_set():
                        raise
            finally:
                stopper.cancel()
                await _cancelled(stopper)
        finally:
            await _maybe_await(client.disconnect())

    def _record_event(self, stamp: datetime) -> None:
        with self._lock:
            current = self._health
            self._health = TelegramRealtimeHealth(
                current.status,
                current.configured_channels,
                current.watched_channels,
                current.events_received + 1,
                utc_datetime(stamp),
                current.last_error_type,
            )

    def _set(self, *, status: str, watched: int, error: str | None) -> None:
        with self._lock:
            current = self._health
            self._health = TelegramRealtimeHealth(
                status,
                current.configured_channels,
                watched,
                current.events_received,
                current.last_event_at,
                error,
            )


async def _deliver(
    accept: Callable[[tuple[TelegramPost, ...]], None], post: TelegramPost,
) -> None:
    for attempt in range(3):
        try:
            accept((post,))
            return
        except Exception:
            if attempt == 2:
                raise
            await asyncio.sleep(0.1)


async def _disconnect_on_stop(client: Any, stop: Event) -> None:
    while not stop.is_set():
        await asyncio.sleep(0.1)
    await _maybe_await(client.disconnect())


async def _cancelled(task: asyncio.Task[Any]) -> None:
    try:
        await task
    except asyncio.CancelledError:
        pass


async def _maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


def _telethon_client(config: TelegramRealtimeConfig) -> Any:
    try:
        from telethon import TelegramClient
    except ImportError as exc:
        raise TelegramRealtimeUnavailable("Telethon runtime is not installed") from exc
    return TelegramClient(
        config.session_path,
        config.api_id,
        config.api_hash,
        proxy=None if config.proxy is None else config.proxy.as_telethon(),
        timeout=10,
        request_retries=2,
        connection_retries=2,
        retry_delay=1,
        auto_reconnect=True,
        sequential_updates=True,
        receive_updates=True,
        catch_up=False,
    )


def _new_message_filter(entities: Sequence[Any]) -> Any:
    try:
        from telethon import events
    except ImportError as exc:
        raise TelegramRealtimeUnavailable("Telethon runtime is not installed") from exc
    return events.NewMessage(chats=list(entities), incoming=True)


__all__ = [
    "TelegramRealtimeHealth",
    "TelegramRealtimeMonitor",
    "TelegramRealtimeUnavailable",
]
