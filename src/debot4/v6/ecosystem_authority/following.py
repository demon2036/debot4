"""Complete cursor-paginated following snapshots through FxTwitter."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping
import urllib.parse

from ..x import FxJsonHttp, FxTwitterError, XCheckpoint
from ..x.http import JsonGetter
from .models import AuthorityNode, FollowingSnapshot


class FollowingError(FxTwitterError):
    """Following response is incomplete or violates identity boundaries."""


@dataclass(slots=True)
class FollowingClient:
    http: JsonGetter = field(default_factory=FxJsonHttp)
    origin: str = "https://api.fxtwitter.com"
    max_pages: int = 40

    def __post_init__(self) -> None:
        parsed = urllib.parse.urlsplit(self.origin)
        if parsed.scheme != "https" or not parsed.hostname or parsed.path.rstrip("/"):
            raise ValueError("FxTwitter origin must be an HTTPS origin")
        if isinstance(self.max_pages, bool) or not 1 <= self.max_pages <= 100:
            raise ValueError("following page limit must be between 1 and 100")
        self.origin = self.origin.rstrip("/")

    def fetch(self, actor: AuthorityNode) -> FollowingSnapshot:
        encoded = urllib.parse.quote(actor.handle, safe="")
        base_url = f"{self.origin}/2/profile/{encoded}/following"
        cursor = ""
        following: dict[str, str] = {}
        hashes: list[str] = []
        observed_at: datetime | None = None
        for _page in range(self.max_pages):
            query = "" if not cursor else "?" + urllib.parse.urlencode({"cursor": cursor})
            document = self.http.get_json(base_url + query)
            if document is None or not document.sha256:
                raise FollowingError("FxTwitter returned an empty following page")
            rows, next_cursor = _parse_page(document.payload)
            observed_at = document.fetched_at
            hashes.append(document.sha256)
            for user_id, handle in rows.items():
                existing = following.get(user_id)
                if existing is not None and existing != handle:
                    raise FollowingError("following stable identity changed within a snapshot")
                following[user_id] = handle
            if not next_cursor:
                return FollowingSnapshot.create(
                    actor=actor,
                    observed_at=observed_at,
                    source_url=base_url,
                    page_hashes=tuple(hashes),
                    following=following,
                )
            cursor = next_cursor
        raise FollowingError("following pagination exceeded the configured limit")


def _parse_page(payload: object) -> tuple[dict[str, str], str]:
    if not isinstance(payload, Mapping) or payload.get("code") != 200:
        raise FollowingError("FxTwitter following schema is invalid")
    rows = payload.get("results")
    cursor = payload.get("cursor")
    if not isinstance(rows, list) or len(rows) > 100 or not isinstance(cursor, Mapping):
        raise FollowingError("FxTwitter following schema is invalid")
    output: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise FollowingError("FxTwitter following row is invalid")
        checkpoint = XCheckpoint(
            str(row.get("screen_name") or ""),
            str(row.get("id") or ""),
        )
        output[checkpoint.user_id] = checkpoint.handle
    bottom = str(cursor.get("bottom") or "").strip()
    next_cursor = "" if not bottom or bottom.startswith("0|") else bottom
    return output, next_cursor
