from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from debot4.v6.telegram.realtime import TelegramRealtimeMonitor
from debot4.v6.telegram.realtime_config import (
    SCHEMA,
    TelegramProxyConfig,
    TelegramRealtimeConfig,
    TelegramRealtimeConfigError,
    load_telegram_realtime_config,
)


NOW = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


def _session(tmp_path: Path) -> Path:
    path = tmp_path / "monitor.session"
    path.write_bytes(b"private-session")
    path.chmod(0o600)
    return path


def _config(tmp_path: Path) -> TelegramRealtimeConfig:
    return TelegramRealtimeConfig(
        _session(tmp_path),
        12345,
        "a" * 32,
        TelegramProxyConfig("socks5", "127.0.0.1", 10808),
    )


def test_private_config_loads_without_exposing_hash_or_path_in_public_state(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    config_path = tmp_path / "runtime.json"
    config_path.write_text(json.dumps({
        "schema": SCHEMA,
        "session_path": str(session),
        "api_id": 12345,
        "api_hash": "b" * 32,
        "proxy": {
            "proxy_type": "socks5",
            "addr": "127.0.0.1",
            "port": 10808,
            "rdns": True,
        },
    }), encoding="utf-8")
    config_path.chmod(0o600)

    config = load_telegram_realtime_config(config_path)

    assert config.session_path == session.resolve()
    assert config.proxy.as_telethon()["port"] == 10808
    assert "b" * 32 not in repr(config)


def test_config_and_session_must_both_be_private_regular_files(
    tmp_path: Path,
) -> None:
    session = _session(tmp_path)
    session.chmod(0o644)
    with pytest.raises(TelegramRealtimeConfigError, match="unsafe"):
        TelegramRealtimeConfig(session, 12345, "a" * 32)


class FakeClient:
    def __init__(self, events: list[object], *, authorized: bool = True) -> None:
        self.events = events
        self.authorized = authorized
        self.handler = None
        self.filter = None
        self.disconnected = False

    async def connect(self) -> None:
        return None

    async def is_user_authorized(self) -> bool:
        return self.authorized

    async def get_entity(self, channel: str) -> object:
        number = {"yndegen": 101, "pote_korea": 102}[channel]
        return SimpleNamespace(id=number, username=channel)

    def add_event_handler(self, handler: object, event_filter: object) -> None:
        self.handler = handler
        self.filter = event_filter

    async def run_until_disconnected(self) -> None:
        for event in self.events:
            await self.handler(event)
        while not self.disconnected:
            await _pause()

    async def disconnect(self) -> None:
        self.disconnected = True


class CancelledOnDisconnectClient(FakeClient):
    async def run_until_disconnected(self) -> None:
        while not self.disconnected:
            await _pause()
        import asyncio
        raise asyncio.CancelledError


async def _pause() -> None:
    import asyncio
    await asyncio.sleep(0.01)


def _event(channel: str, message_id: int) -> object:
    message = SimpleNamespace(
        id=message_id,
        message=f"Narrative {TOKEN} https://example.com/source",
        date=NOW,
        media=None,
        peer_id=SimpleNamespace(channel_id=101),
        get_entities_text=lambda: [],
    )
    return SimpleNamespace(
        message=message,
        id=message_id,
        raw_text=message.message,
        chat=SimpleNamespace(username=channel),
    )


def test_realtime_stream_accepts_only_reviewed_channels_and_stops_cleanly(
    tmp_path: Path,
) -> None:
    client = FakeClient([_event("not_reviewed", 1), _event("Yndegen", 2)])
    monitor = TelegramRealtimeMonitor(
        _config(tmp_path),
        ("Yndegen", "pote_korea"),
        retry_seconds=0.05,
        clock=lambda: NOW,
        client_factory=lambda _config: client,
        event_filter_factory=lambda entities: tuple(item.id for item in entities),
    )
    stop = Event()
    delivered = Event()
    accepted = []

    def accept(posts: tuple[object, ...]) -> None:
        accepted.extend(posts)
        delivered.set()

    thread = Thread(target=monitor.run, args=(stop, accept))
    thread.start()
    assert delivered.wait(1)
    stop.set()
    thread.join(2)

    assert not thread.is_alive()
    assert len(accepted) == 1
    post = accepted[0]
    assert post.channel == "yndegen" and post.message_id == 2
    assert post.bsc_contracts == (TOKEN,)
    assert client.filter == (101, 102)
    health = monitor.snapshot()
    assert health.status == "stopped" and health.events_received == 1
    assert health.last_event_at == NOW


def test_unauthorized_session_retries_and_reports_only_error_type(
    tmp_path: Path,
) -> None:
    attempts = 0
    retried = Event()

    def factory(_config: object) -> FakeClient:
        nonlocal attempts
        attempts += 1
        if attempts >= 2:
            retried.set()
        return FakeClient([], authorized=False)

    monitor = TelegramRealtimeMonitor(
        _config(tmp_path),
        ("Yndegen",),
        retry_seconds=0.05,
        client_factory=factory,
        event_filter_factory=lambda _entities: object(),
    )
    stop = Event()
    thread = Thread(target=monitor.run, args=(stop, lambda _posts: None))
    thread.start()
    assert retried.wait(1)
    stop.set()
    thread.join(2)

    assert attempts >= 2
    assert monitor.snapshot().last_error_type == "TelegramRealtimeUnavailable"
    assert "unauthorized" not in json.dumps(monitor.snapshot().as_public_dict())


def test_telethon_cancellation_on_requested_disconnect_is_a_clean_stop(
    tmp_path: Path,
) -> None:
    client = CancelledOnDisconnectClient([])
    monitor = TelegramRealtimeMonitor(
        _config(tmp_path),
        ("Yndegen",),
        retry_seconds=0.05,
        client_factory=lambda _config: client,
        event_filter_factory=lambda _entities: object(),
    )
    stop = Event()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            monitor.run(stop, lambda _posts: None)
        except BaseException as exc:
            errors.append(exc)

    thread = Thread(target=run)
    thread.start()
    for _attempt in range(100):
        if monitor.snapshot().status == "live":
            break
        stop.wait(0.01)
    stop.set()
    thread.join(2)

    assert not thread.is_alive()
    assert errors == []
    assert monitor.snapshot().status == "stopped"
