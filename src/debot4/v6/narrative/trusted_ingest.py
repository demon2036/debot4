"""The only X/FxTwitter adapter allowed to issue sealed narrative receipts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .actors import ActorRef
from .fxtwitter import (
    FxTwitterClient,
    FxTwitterObservation,
    parse_x_status_url,
)
from .investigation_domain import EvidenceProvider
from .investigation_inputs import NarrativeEvent
from .source_receipts import (
    VerifiedSourceReceipt,
    _TRUSTED_RECEIPT_ISSUER,
)
from .trusted_events import events_from_verified_source


class TrustedIngestError(RuntimeError):
    """The provider observation could not satisfy the trusted boundary."""


class FxObservationFetcher(Protocol):
    def fetch_observation(self, status_url: str) -> FxTwitterObservation: ...


@dataclass(frozen=True, slots=True)
class VerifiedXStatus:
    receipt: VerifiedSourceReceipt
    actor: ActorRef

    @property
    def text(self) -> str:
        return self.receipt._content


@dataclass(slots=True)
class XStatusVerifier:
    fetcher: FxObservationFetcher = field(default_factory=FxTwitterClient)
    registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY

    def verify(self, status_url: str) -> VerifiedXStatus:
        requested_handle, requested_id = parse_x_status_url(status_url)
        observation = self.fetcher.fetch_observation(status_url)
        tweet = observation.tweet
        if tweet.tweet_id != requested_id:
            raise TrustedIngestError("provider status identity mismatch")
        if tweet.author_handle.casefold() != requested_handle.casefold():
            raise TrustedIngestError("provider author handle mismatch")
        if not tweet.author_id:
            raise TrustedIngestError("provider stable author identity missing")
        try:
            receipt = _TRUSTED_RECEIPT_ISSUER.x_status(
                provider=EvidenceProvider.FXTWITTER,
                status_id=tweet.tweet_id,
                author_id=tweet.author_id,
                author_handle=tweet.author_handle,
                content=tweet.text,
                published_at=tweet.published_at,
                fetched_at=tweet.fetched_at,
                raw_payload=observation.raw_payload,
                response_identity=observation.response_identity,
            )
        except ValueError as exc:
            raise TrustedIngestError(str(exc)) from None
        actor = self.registry.resolve(tweet.author_handle)
        if not self.registry.permits(
            actor, receipt.author_handle, receipt.author_id,
            receipt.canonical_url, "",
        ):
            raise TrustedIngestError("actor identity is not registered or verified")
        return VerifiedXStatus(receipt, actor)


def events_from_verified_status(
    status: VerifiedXStatus,
    narrative_key: str,
) -> tuple[NarrativeEvent, ...]:
    """Derive all event labels from sealed content; callers cannot self-label."""

    return events_from_verified_source(status.actor, status.receipt, narrative_key)
