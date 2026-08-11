"""Direct public Telegram channel reader and exact-message verifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
from urllib.parse import quote

from .http import TelegramHtmlGetter, TelegramHtmlHttp
from .models import (
    TelegramChannelBatch,
    TelegramCheckpoint,
    TelegramPost,
    TelegramPostObservation,
    telegram_channel,
)
from .parser import parse_telegram_page


class TelegramUnavailable(RuntimeError):
    """A Telegram reference is not a public readable channel/message."""


@dataclass(slots=True)
class TelegramPublicClient:
    http: TelegramHtmlGetter = field(default_factory=TelegramHtmlHttp)

    def poll(
        self,
        channel: str,
        checkpoint: TelegramCheckpoint | None = None,
    ) -> TelegramChannelBatch:
        normalized = telegram_channel(channel)
        if checkpoint is not None and checkpoint.channel != normalized:
            raise ValueError("Telegram checkpoint belongs to another channel")
        document = self.http.get_html(
            f"https://t.me/s/{quote(normalized, safe='')}"
        )
        page = parse_telegram_page(document.html, normalized, document.fetched_at)
        if not page.is_public_channel:
            raise TelegramUnavailable("Telegram reference is not a public channel")
        latest = max(
            (item.message_id for item in page.posts),
            default=checkpoint.latest_message_id if checkpoint is not None else 0,
        )
        return TelegramChannelBatch(
            page.posts, TelegramCheckpoint(normalized, latest), len(page.posts)
        )

    def get_message(self, channel: str, message_id: int) -> TelegramPost:
        return self.get_observation(channel, message_id).post

    def get_observation(
        self, channel: str, message_id: int
    ) -> TelegramPostObservation:
        normalized = telegram_channel(channel)
        if isinstance(message_id, bool) or message_id <= 0:
            raise ValueError("invalid Telegram message ID")
        document = self.http.get_html(
            f"https://t.me/{quote(normalized, safe='')}/{message_id}"
            "?embed=1&mode=tme"
        )
        page = parse_telegram_page(document.html, normalized, document.fetched_at)
        for post in page.posts:
            if post.message_id == message_id:
                raw = document.html.encode("utf-8")
                identity = (
                    f"telegram:{normalized}:{message_id}:"
                    f"{sha256(raw).hexdigest()}"
                )
                return TelegramPostObservation(post, raw, identity)
        raise TelegramUnavailable("exact Telegram message was not found")
