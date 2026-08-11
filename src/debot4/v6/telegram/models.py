"""Immutable values at the public Telegram HTML boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from ..identity import bsc_address, utc_datetime


_CHANNEL = re.compile(r"[A-Za-z0-9_]{5,32}")


def telegram_channel(value: str) -> str:
    channel = value.strip().lstrip("@").casefold()
    if not _CHANNEL.fullmatch(channel):
        raise ValueError("invalid public Telegram channel")
    return channel


@dataclass(frozen=True, slots=True)
class TelegramPost:
    channel: str
    message_id: int
    text: str
    created_at: datetime
    fetched_at: datetime
    urls: tuple[str, ...] = ()
    bsc_contracts: tuple[str, ...] = ()
    has_media: bool = False

    def __post_init__(self) -> None:
        channel = telegram_channel(self.channel)
        text = self.text.strip()
        if isinstance(self.message_id, bool) or self.message_id <= 0:
            raise ValueError("invalid Telegram message ID")
        if not text and not self.has_media:
            raise ValueError("Telegram message requires text or media")
        object.__setattr__(self, "channel", channel)
        object.__setattr__(self, "text", text)
        object.__setattr__(self, "created_at", utc_datetime(self.created_at))
        object.__setattr__(self, "fetched_at", utc_datetime(self.fetched_at))
        object.__setattr__(self, "urls", tuple(dict.fromkeys(self.urls)))
        object.__setattr__(self, "bsc_contracts", tuple(dict.fromkeys(
            bsc_address(item) for item in self.bsc_contracts
        )))

    @property
    def canonical_url(self) -> str:
        return f"https://t.me/{self.channel}/{self.message_id}"

    @property
    def source_id(self) -> str:
        return f"telegram:{self.channel}:{self.message_id}"


@dataclass(frozen=True, slots=True)
class TelegramPostObservation:
    """Exact public-message response retained for trusted verification."""

    post: TelegramPost
    raw_payload: bytes
    response_identity: str

    def __post_init__(self) -> None:
        identity = self.response_identity.strip()
        if not isinstance(self.raw_payload, bytes) or not self.raw_payload:
            raise ValueError("Telegram observation requires raw response bytes")
        if not identity:
            raise ValueError("Telegram observation requires response identity")
        object.__setattr__(self, "response_identity", identity)


@dataclass(frozen=True, slots=True)
class TelegramCheckpoint:
    channel: str
    latest_message_id: int = 0

    def __post_init__(self) -> None:
        channel = telegram_channel(self.channel)
        if isinstance(self.latest_message_id, bool) or self.latest_message_id < 0:
            raise ValueError("invalid Telegram checkpoint message ID")
        object.__setattr__(self, "channel", channel)


@dataclass(frozen=True, slots=True)
class TelegramChannelBatch:
    posts: tuple[TelegramPost, ...]
    checkpoint: TelegramCheckpoint
    fetched_items: int

    def __post_init__(self) -> None:
        if self.fetched_items < 0:
            raise ValueError("invalid Telegram batch accounting")
        if any(item.channel != self.checkpoint.channel for item in self.posts):
            raise ValueError("Telegram batch crossed channel boundary")
        object.__setattr__(self, "posts", tuple(self.posts))
