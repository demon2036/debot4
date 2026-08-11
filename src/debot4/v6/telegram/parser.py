"""Parse public Telegram channel HTML without browser automation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from html.parser import HTMLParser
import re
from urllib.parse import urljoin, urlsplit

from .models import TelegramPost, telegram_channel


_ADDRESS = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")
_URL = re.compile(r"https?://[^\s<>'\"]+")
_VOID = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"})
_MEDIA_MARKERS = (
    "message_photo", "message_video", "message_document", "message_voice",
    "message_poll", "message_sticker", "message_gif",
)


class TelegramPageError(ValueError):
    """The HTML is not a valid public channel/message page."""


@dataclass(frozen=True, slots=True)
class TelegramPage:
    posts: tuple[TelegramPost, ...]
    is_public_channel: bool


@dataclass(slots=True)
class _Message:
    channel: str
    message_id: int
    text_parts: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    created_at: str = ""
    has_media: bool = False


class _PageParser(HTMLParser):
    def __init__(self, expected_channel: str, fetched_at: datetime) -> None:
        super().__init__(convert_charrefs=True)
        self.expected_channel = telegram_channel(expected_channel)
        self.fetched_at = fetched_at
        self.posts: list[TelegramPost] = []
        self.is_public_channel = False
        self._message: _Message | None = None
        self._depth = 0
        self._text_depth: int | None = None

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]],
    ) -> None:
        values = {key: value or "" for key, value in attrs}
        classes = frozenset(values.get("class", "").split())
        if "tgme_channel_info" in classes or "tgme_channel_history" in classes:
            self.is_public_channel = True
        if self._message is None:
            identity = values.get("data-post", "")
            if tag == "div" and identity:
                self._start_message(identity)
                self._inspect(tag, values, classes)
            return
        if tag not in _VOID:
            self._depth += 1
        self._inspect(tag, values, classes)

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]],
    ) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._message is None or tag in _VOID:
            return
        if self._text_depth == self._depth and tag == "div":
            self._text_depth = None
        self._depth -= 1
        if self._depth == 0:
            self._finish_message()

    def handle_data(self, data: str) -> None:
        if self._message is not None and self._text_depth is not None:
            self._message.text_parts.append(data)

    def _start_message(self, identity: str) -> None:
        try:
            channel, raw_id = identity.rsplit("/", 1)
            normalized = telegram_channel(channel)
            message_id = int(raw_id)
        except (TypeError, ValueError):
            return
        if normalized != self.expected_channel or message_id <= 0:
            return
        self._message = _Message(normalized, message_id)
        self._depth = 1
        self._text_depth = None

    def _inspect(
        self, tag: str, values: dict[str, str], classes: frozenset[str],
    ) -> None:
        if self._message is None:
            return
        class_text = " ".join(classes)
        if "js-message_text" in classes and "js-message_reply_text" not in classes:
            self._text_depth = self._depth
        if tag == "br" and self._text_depth is not None:
            self._message.text_parts.append("\n")
        if tag == "a" and self._text_depth is not None and values.get("href"):
            url = _safe_url(urljoin("https://t.me", values["href"]))
            if url:
                self._message.urls.append(url)
        if tag == "time" and values.get("datetime"):
            self._message.created_at = values["datetime"]
        if any(marker in class_text for marker in _MEDIA_MARKERS):
            self._message.has_media = True

    def _finish_message(self) -> None:
        item = self._message
        self._message = None
        self._depth = 0
        self._text_depth = None
        if item is None or not item.created_at:
            return
        try:
            created_at = datetime.fromisoformat(item.created_at.replace("Z", "+00:00"))
            text = _clean_text("".join(item.text_parts))
            urls = tuple(dict.fromkeys((*item.urls, *(_URL.findall(text)))))
            contracts = tuple(match.group(0) for match in _ADDRESS.finditer(text))
            post = TelegramPost(
                item.channel, item.message_id, text, created_at, self.fetched_at,
                urls, contracts, item.has_media,
            )
        except (TypeError, ValueError):
            return
        self.posts.append(post)


def parse_telegram_page(
    html: str, expected_channel: str, fetched_at: datetime,
) -> TelegramPage:
    parser = _PageParser(expected_channel, fetched_at)
    try:
        parser.feed(html)
        parser.close()
    except (TypeError, ValueError) as exc:
        raise TelegramPageError("invalid Telegram HTML") from exc
    posts = {item.message_id: item for item in parser.posts}
    return TelegramPage(
        tuple(posts[key] for key in sorted(posts)), parser.is_public_channel
    )


def _clean_text(value: str) -> str:
    lines = (" ".join(line.split()) for line in value.splitlines())
    return "\n".join(line for line in lines if line).strip()


def _safe_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return ""
    return value
