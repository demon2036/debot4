"""Immutable review ledger for exact-CA X evidence associations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping

from .x_post_semantics import XPostSemantic


class XPostOrigin(str, Enum):
    PROJECT = "project"
    INDEPENDENT = "independent"
    AUTOMATION = "automation"
    RELAY = "relay"
    MALICIOUS = "malicious"


@dataclass(frozen=True, slots=True)
class ReviewedXAssociation:
    tweet_id: str
    address: str
    label: str
    author_handle: str
    published_at: str
    semantic: XPostSemantic
    origin: XPostOrigin
    reason: str
    status_url: str
    status_payload_sha256: str
    text_sha256: str


def validate_and_join_x_reviews(
    evidence_rows: Iterable[Mapping[str, object]],
    review_rows: Iterable[Mapping[str, object]],
) -> tuple[ReviewedXAssociation, ...]:
    """Require exactly one valid manual review for each tweet/CA association."""

    evidence = _index(evidence_rows, "evidence")
    reviews = _index(review_rows, "review")
    missing = sorted(evidence.keys() - reviews.keys())
    extra = sorted(reviews.keys() - evidence.keys())
    if missing or extra:
        raise ValueError(
            f"review coverage mismatch: missing={missing}, extra={extra}"
        )
    return tuple(_join(evidence[key], reviews[key]) for key in evidence)


def _index(
    rows: Iterable[Mapping[str, object]], source: str,
) -> dict[tuple[str, str], Mapping[str, object]]:
    indexed: dict[tuple[str, str], Mapping[str, object]] = {}
    for row in rows:
        key = _key(row)
        if key in indexed:
            raise ValueError(f"duplicate {source} association: {key}")
        indexed[key] = row
    return indexed


def _key(row: Mapping[str, object]) -> tuple[str, str]:
    tweet_id = str(row.get("tweet_id", "")).strip()
    address = str(row.get("address", "")).strip().lower()
    if not tweet_id or not address:
        raise ValueError("tweet_id and address are required")
    return tweet_id, address


def _join(
    evidence: Mapping[str, object], review: Mapping[str, object],
) -> ReviewedXAssociation:
    reason = str(review.get("reason", "")).strip()
    if not reason:
        raise ValueError(f"review reason is required for {_key(review)}")
    try:
        semantic = XPostSemantic(str(review.get("semantic", "")))
        origin = XPostOrigin(str(review.get("origin", "")))
    except ValueError as exc:
        raise ValueError(f"invalid review enum for {_key(review)}") from exc
    return ReviewedXAssociation(
        tweet_id=_key(evidence)[0],
        address=_key(evidence)[1],
        label=str(evidence["label"]),
        author_handle=str(evidence["author_handle"]),
        published_at=str(evidence["published_at"]),
        semantic=semantic,
        origin=origin,
        reason=reason,
        status_url=str(evidence["status_url"]),
        status_payload_sha256=str(evidence["status_payload_sha256"]),
        text_sha256=str(evidence["text_sha256"]),
    )
