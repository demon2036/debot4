"""Pure conversion from an authenticated Telegram event to a domain post."""

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Sequence

from .models import TelegramPost, telegram_channel


_ADDRESS = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
_URL = re.compile(r"https?://[^\s<>'\"]+")


def event_post(
    event: Any,
    channel_by_id: dict[int, str],
    allowed_channels: Sequence[str],
    fetched_at: datetime,
) -> TelegramPost | None:
    message = getattr(event, "message", event)
    channel = _event_channel(event, message, channel_by_id)
    if channel not in allowed_channels:
        return None
    message_id = getattr(message, "id", getattr(event, "id", 0))
    text = str(getattr(event, "raw_text", None) or getattr(message, "message", ""))
    created_at = getattr(message, "date", getattr(event, "date", None))
    if not isinstance(created_at, datetime):
        return None
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    urls = tuple(dict.fromkeys((*_URL.findall(text), *_entity_urls(message))))
    contracts = tuple(item.group(0) for item in _ADDRESS.finditer(text))
    has_media = getattr(message, "media", None) is not None
    try:
        return TelegramPost(
            channel, int(message_id), text, created_at, fetched_at,
            urls, contracts, has_media,
        )
    except (TypeError, ValueError):
        return None


def _event_channel(
    event: Any, message: Any, channel_by_id: dict[int, str],
) -> str:
    username = getattr(getattr(event, "chat", None), "username", None)
    if isinstance(username, str) and username:
        try:
            return telegram_channel(username)
        except ValueError:
            return ""
    peer = getattr(message, "peer_id", None)
    raw_id = getattr(peer, "channel_id", None)
    try:
        return channel_by_id.get(int(raw_id), "")
    except (TypeError, ValueError):
        return ""


def _entity_urls(message: Any) -> tuple[str, ...]:
    method = getattr(message, "get_entities_text", None)
    if not callable(method):
        return ()
    found: list[str] = []
    try:
        pairs = method()
    except Exception:
        return ()
    for entity, text in pairs:
        value = getattr(entity, "url", None)
        candidate = value if isinstance(value, str) else text
        if isinstance(candidate, str) and _URL.fullmatch(candidate.strip()):
            found.append(candidate.strip())
    return tuple(dict.fromkeys(found))


__all__ = ["event_post"]
