"""Pure restart decisions for append-only Grok research journals."""

from __future__ import annotations

import json
from typing import Iterable


_REFUSAL_MARKERS = (
    "cannot comply",
    "can't comply",
    "will not generate",
    "will not perform",
    "will not search",
)


def row_is_research_success(row: dict[str, object]) -> bool:
    """Reject transport-level successes whose answer explicitly refused the task."""

    if row.get("status") != "success":
        return False
    answer = str(row.get("answer") or "").casefold()
    return not any(marker in answer for marker in _REFUSAL_MARKERS)


def successful_prompt_digests(lines: Iterable[str]) -> dict[str, str]:
    """Return the newest successful prompt digest for every task key."""

    completed: dict[str, str] = {}
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not row_is_research_success(row):
            continue
        key = str(row.get("key") or "").strip()
        digest = str(row.get("prompt_sha256") or "").strip().casefold()
        if key and digest:
            completed[key] = digest
    return completed


def prompt_is_complete(completed: dict[str, str], key: str, digest: str) -> bool:
    """A reused key is complete only when its exact prompt already succeeded."""

    return completed.get(key) == digest.casefold()


def successful_candidate_urls(lines: Iterable[str]) -> tuple[str, ...]:
    """Keep every URL from successful append-only scans, including older batches."""

    urls: set[str] = set()
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        if not row_is_research_success(row):
            continue
        urls.update(
            str(value).strip()
            for value in row.get("candidate_urls", ())
            if str(value).strip()
        )
    return tuple(sorted(urls))


def reusable_x_verification_rows(
    lines: Iterable[str], *, desired_urls: Iterable[str], schema: str,
) -> dict[str, dict[str, object]]:
    """Reuse terminal direct-X checks; transient unavailable rows must be retried."""

    desired = {str(value).strip() for value in desired_urls if str(value).strip()}
    rows: dict[str, dict[str, object]] = {}
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        url = str(row.get("status_url") or "").strip()
        if (
            url in desired
            and row.get("schema") == schema
            and row.get("status") in {"verified", "status_author_mismatch"}
        ):
            rows[url] = row
    return rows
