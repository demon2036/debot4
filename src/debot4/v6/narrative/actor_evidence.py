"""Strict onboarding gate for model-discovered X actor evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..x import XProfile
from .fxtwitter import FxTwitterTweet, parse_x_status_url


class ProfileFetcher(Protocol):
    def fetch(self, handle: str) -> XProfile: ...


class StatusFetcher(Protocol):
    def fetch_status(self, status_url: str) -> FxTwitterTweet: ...


@dataclass(frozen=True, slots=True)
class ActorEvidenceCandidate:
    claimed_handle: str
    status_url: str

    def __post_init__(self) -> None:
        handle = self.claimed_handle.strip().lstrip("@").casefold()
        path_handle, status_id = parse_x_status_url(self.status_url)
        object.__setattr__(self, "claimed_handle", handle)
        object.__setattr__(
            self,
            "status_url",
            f"https://x.com/{path_handle}/status/{status_id}",
        )


@dataclass(frozen=True, slots=True)
class ActorEvidenceFinding:
    claimed_handle: str
    status_url: str
    status: str
    observed_handle: str = ""
    observed_author_id: str = ""
    profile_user_id: str = ""
    canonical_url: str = ""
    text: str = ""
    error_type: str = ""

    @property
    def verified(self) -> bool:
        return self.status == "verified"


def verify_actor_evidence(
    candidate: ActorEvidenceCandidate,
    *,
    profiles: ProfileFetcher,
    statuses: StatusFetcher,
) -> ActorEvidenceFinding:
    """Require the claimed handle, URL path, tweet author, and profile ID to agree."""
    path_handle, _ = parse_x_status_url(candidate.status_url)
    base = {
        "claimed_handle": candidate.claimed_handle,
        "status_url": candidate.status_url,
    }
    if path_handle.casefold() != candidate.claimed_handle:
        return ActorEvidenceFinding(**base, status="url_handle_mismatch")
    try:
        tweet = statuses.fetch_status(candidate.status_url)
    except Exception as exc:
        return ActorEvidenceFinding(
            **base, status="status_unavailable", error_type=type(exc).__name__
        )
    observed = tweet.author_handle.casefold()
    observed_id = (tweet.author_id or "").strip()
    observed_fields = {
        "observed_handle": observed,
        "observed_author_id": observed_id,
        "canonical_url": tweet.canonical_url,
        "text": tweet.text,
    }
    if observed != candidate.claimed_handle:
        return ActorEvidenceFinding(
            **base, **observed_fields, status="status_author_mismatch"
        )
    if not observed_id:
        return ActorEvidenceFinding(
            **base, **observed_fields, status="status_author_id_missing"
        )
    try:
        profile = profiles.fetch(candidate.claimed_handle)
    except Exception as exc:
        return ActorEvidenceFinding(
            **base,
            **observed_fields,
            status="profile_unavailable",
            error_type=type(exc).__name__,
        )
    if profile.handle.casefold() != candidate.claimed_handle:
        return ActorEvidenceFinding(
            **base,
            **observed_fields,
            profile_user_id=profile.user_id,
            status="profile_handle_mismatch",
        )
    status = "verified" if profile.user_id == observed_id else "stable_id_mismatch"
    return ActorEvidenceFinding(
        **base,
        **observed_fields,
        profile_user_id=profile.user_id,
        status=status,
    )
