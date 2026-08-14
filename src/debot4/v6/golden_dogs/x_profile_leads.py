"""Pure extraction of X profile candidates from successful Grok journals."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Iterable
from urllib.parse import urlsplit

from .grok_journal import row_is_research_success


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_HOSTS = frozenset({"x.com", "www.x.com", "twitter.com", "www.twitter.com"})
_RESERVED = frozenset({
    "about", "compose", "explore", "hashtag", "home", "i", "intent", "jobs",
    "login", "messages", "privacy", "search", "settings", "share", "tos",
})


@dataclass(frozen=True, slots=True)
class XProfileLead:
    handle: str
    candidate_urls: tuple[str, ...]
    task_keys: tuple[str, ...]


def profile_handle_from_url(value: str) -> str | None:
    """Return a syntactically valid profile handle from an X/profile-or-status URL."""

    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return None
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in _HOSTS:
        return None
    segments = tuple(item for item in parsed.path.split("/") if item)
    if not segments or not _HANDLE.fullmatch(segments[0]):
        return None
    handle = segments[0].casefold()
    return None if handle in _RESERVED else handle


def successful_profile_leads(lines: Iterable[str]) -> tuple[XProfileLead, ...]:
    """Collect handles without treating the model's identity claim as evidence."""

    grouped: dict[str, dict[str, set[str]]] = {}
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not row_is_research_success(row):
            continue
        key = str(row.get("key") or "").strip()
        for value in row.get("candidate_urls", ()):
            url = str(value).strip()
            handle = profile_handle_from_url(url)
            if handle is None:
                continue
            item = grouped.setdefault(handle, {"urls": set(), "keys": set()})
            item["urls"].add(url)
            if key:
                item["keys"].add(key)
    return tuple(
        XProfileLead(handle, tuple(sorted(item["urls"])), tuple(sorted(item["keys"])))
        for handle, item in sorted(grouped.items())
    )
