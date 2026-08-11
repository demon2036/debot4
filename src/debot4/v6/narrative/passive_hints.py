"""Immediate verification of X status hints carried by passive triggers."""

from __future__ import annotations

from dataclasses import dataclass

from .fxtwitter import FxTwitterError, parse_x_status_url
from .trusted_ingest import VerifiedXStatus, XStatusVerifier


@dataclass(frozen=True, slots=True)
class VerifiedTriggerHints:
    statuses: tuple[VerifiedXStatus, ...]
    failed_urls: tuple[str, ...]

    def prompt_context(self) -> str:
        if not self.statuses:
            return ""
        lines = ["FxTwitter 已即时核验的触发原帖（优先于 Grok 索引）："]
        for status in self.statuses:
            receipt = status.receipt
            lines.extend((
                f"- URL: {receipt.canonical_url}",
                f"  author: @{receipt.author_handle} ({receipt.author_id})",
                f"  published_at: {receipt.published_at.isoformat()}",
                f"  content: {status.text[:4_000]}",
            ))
        return "\n".join(lines)


def verify_trigger_hints(
    urls: tuple[str, ...],
    verifier: XStatusVerifier,
    *,
    max_statuses: int = 6,
) -> VerifiedTriggerHints:
    """Verify only allowlisted X status URLs; keep other URLs as search hints."""

    statuses: list[VerifiedXStatus] = []
    failed: list[str] = []
    seen: set[str] = set()
    for url in urls:
        try:
            parse_x_status_url(url)
        except FxTwitterError:
            continue
        key = url.casefold()
        if key in seen or len(statuses) >= max_statuses:
            continue
        seen.add(key)
        try:
            statuses.append(verifier.verify(url))
        except Exception:
            failed.append(url)
    return VerifiedTriggerHints(
        tuple(statuses), tuple(dict.fromkeys(failed))
    )
