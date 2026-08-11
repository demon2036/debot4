"""Canonical text extraction for FxTwitter status payloads."""

from __future__ import annotations

from typing import Mapping


MAX_X_CONTENT_CHARS = 100_000


def content_text(row: Mapping[str, object]) -> str:
    """Preserve non-plain-text X content without inventing endorsement text."""

    text = str(row.get("text") or "").strip()
    if text:
        return text[:MAX_X_CONTENT_CHARS]
    article = row.get("article")
    if isinstance(article, Mapping):
        parts = _object_text(article, ("title", "preview_text", "description"))
        if parts:
            return "[article]\n" + "\n".join(parts)
    quote = row.get("quote")
    if isinstance(quote, Mapping):
        return "[quote-only post]"
    card = row.get("card")
    if isinstance(card, Mapping):
        parts = _object_text(card, ("title", "description", "name"))
        if parts:
            return "[card]\n" + "\n".join(parts)
    poll = row.get("poll")
    if isinstance(poll, Mapping):
        parts = _object_text(poll, ("question", "name"))
        return "[poll]" + ("\n" + "\n".join(parts) if parts else "")
    media = row.get("media")
    if isinstance(media, Mapping) and any(
        media.get(key) for key in ("all", "photos", "videos")
    ):
        return "[media-only post]"
    raw = row.get("raw_text")
    if isinstance(raw, Mapping):
        fallback = str(raw.get("text") or "").strip()
        if fallback:
            return fallback[:MAX_X_CONTENT_CHARS]
    return "[non-text post]"


def _object_text(
    value: Mapping[str, object], keys: tuple[str, ...]
) -> tuple[str, ...]:
    parts = [str(value.get(key) or "").strip() for key in keys]
    return tuple(dict.fromkeys(
        part[:MAX_X_CONTENT_CHARS] for part in parts if part
    ))
