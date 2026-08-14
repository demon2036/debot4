"""Pure provenance checks for X statuses returned by per-account research tasks."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Iterable, Mapping

from ..narrative.fxtwitter import FxTwitterError, parse_x_status_url
from .grok_journal import row_is_research_success


def expected_authors_by_status_id(
    lines: Iterable[str],
) -> dict[str, frozenset[str]]:
    """Map each model-suggested status ID to the task's independently known user ID."""

    grouped: dict[str, set[str]] = {}
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not row_is_research_success(row):
            continue
        expected_id = str(row.get("stable_user_id") or "").strip()
        if not expected_id:
            continue
        for value in row.get("candidate_urls", ()):
            try:
                _, status_id = parse_x_status_url(str(value).strip())
            except FxTwitterError:
                continue
            grouped.setdefault(status_id, set()).add(expected_id)
    return {
        status_id: frozenset(author_ids)
        for status_id, author_ids in sorted(grouped.items())
    }


def scope_verified_status(
    row: Mapping[str, object],
    *,
    expected_authors: Mapping[str, frozenset[str]],
    window_start: datetime,
    window_end_exclusive: datetime,
) -> tuple[str, tuple[str, ...]]:
    """Return a provenance verdict without treating model output as identity evidence."""

    if row.get("status") != "verified":
        return "direct_x_unavailable", ()
    status_id = _status_id(row)
    allowed = tuple(sorted(expected_authors.get(status_id, ())))
    observed_id = str(row.get("observed_author_id") or "").strip()
    if not status_id or not allowed or observed_id not in allowed:
        return "task_author_mismatch", allowed
    published_at = _timestamp(row.get("published_at"))
    if published_at is None:
        return "published_at_invalid", allowed
    start = _aware_utc(window_start)
    end = _aware_utc(window_end_exclusive)
    if not start <= published_at < end:
        return "outside_scan_window", allowed
    return "accepted", allowed


def _status_id(row: Mapping[str, object]) -> str:
    value = str(row.get("canonical_url") or row.get("status_url") or "").strip()
    try:
        return parse_x_status_url(value)[1]
    except FxTwitterError:
        return ""


def _timestamp(value: object) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return _aware_utc(parsed)
    except (TypeError, ValueError):
        return None


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scan window must be timezone-aware")
    return value.astimezone(timezone.utc)
