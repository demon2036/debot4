"""Private, file-backed configuration for Telegram user-session monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import stat
from typing import Any


SCHEMA = "debot4.telegram-realtime.v1"
_API_HASH = re.compile(r"[0-9a-fA-F]{32}")
_ROOT_KEYS = frozenset({"schema", "session_path", "api_id", "api_hash", "proxy"})
_PROXY_KEYS = frozenset({"proxy_type", "addr", "port", "rdns"})


class TelegramRealtimeConfigError(ValueError):
    """The private Telegram runtime configuration is absent or unsafe."""


@dataclass(frozen=True, slots=True)
class TelegramProxyConfig:
    proxy_type: str
    addr: str
    port: int
    rdns: bool = True

    def __post_init__(self) -> None:
        proxy_type = self.proxy_type.strip().casefold()
        addr = self.addr.strip()
        if proxy_type != "socks5" or not addr:
            raise TelegramRealtimeConfigError("unsupported Telegram proxy")
        if type(self.port) is not int or not 1 <= self.port <= 65_535:
            raise TelegramRealtimeConfigError("invalid Telegram proxy port")
        if type(self.rdns) is not bool:
            raise TelegramRealtimeConfigError("invalid Telegram proxy rdns flag")
        object.__setattr__(self, "proxy_type", proxy_type)
        object.__setattr__(self, "addr", addr)

    def as_telethon(self) -> dict[str, object]:
        return {
            "proxy_type": self.proxy_type,
            "addr": self.addr,
            "port": self.port,
            "rdns": self.rdns,
        }


@dataclass(frozen=True, slots=True)
class TelegramRealtimeConfig:
    session_path: Path
    api_id: int
    api_hash: str = field(repr=False)
    proxy: TelegramProxyConfig | None = None

    def __post_init__(self) -> None:
        session = _private_file(self.session_path, maximum_bytes=64 * 1024 * 1024)
        if type(self.api_id) is not int or self.api_id <= 0:
            raise TelegramRealtimeConfigError("invalid Telegram API ID")
        api_hash = self.api_hash.strip()
        if not _API_HASH.fullmatch(api_hash):
            raise TelegramRealtimeConfigError("invalid Telegram API hash")
        object.__setattr__(self, "session_path", session)
        object.__setattr__(self, "api_hash", api_hash)


def load_telegram_realtime_config(path: str | Path) -> TelegramRealtimeConfig:
    """Load a strict private JSON document without exposing its secrets."""

    config_path = _private_file(path, maximum_bytes=16 * 1024)
    try:
        document = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TelegramRealtimeConfigError("invalid Telegram config document") from exc
    if not isinstance(document, dict) or set(document) != _ROOT_KEYS:
        raise TelegramRealtimeConfigError("invalid Telegram config fields")
    if document.get("schema") != SCHEMA:
        raise TelegramRealtimeConfigError("unsupported Telegram config schema")
    proxy = _proxy(document.get("proxy"))
    return TelegramRealtimeConfig(
        session_path=_string(document, "session_path"),
        api_id=document.get("api_id"),
        api_hash=_string(document, "api_hash"),
        proxy=proxy,
    )


def _proxy(value: Any) -> TelegramProxyConfig | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != _PROXY_KEYS:
        raise TelegramRealtimeConfigError("invalid Telegram proxy fields")
    return TelegramProxyConfig(
        proxy_type=_string(value, "proxy_type"),
        addr=_string(value, "addr"),
        port=value.get("port"),
        rdns=value.get("rdns"),
    )


def _string(document: dict[str, Any], key: str) -> str:
    value = document.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TelegramRealtimeConfigError(f"invalid Telegram {key}")
    return value.strip()


def _private_file(path: str | Path, *, maximum_bytes: int) -> Path:
    candidate = Path(path).expanduser()
    try:
        metadata = candidate.lstat()
    except OSError as exc:
        raise TelegramRealtimeConfigError("Telegram private file is unavailable") from exc
    if (
        not stat.S_ISREG(metadata.st_mode)
        or stat.S_ISLNK(metadata.st_mode)
        or metadata.st_mode & 0o077
        or not 0 < metadata.st_size <= maximum_bytes
    ):
        raise TelegramRealtimeConfigError("Telegram private file is unsafe")
    return candidate.resolve()


__all__ = [
    "SCHEMA",
    "TelegramProxyConfig",
    "TelegramRealtimeConfig",
    "TelegramRealtimeConfigError",
    "load_telegram_realtime_config",
]
