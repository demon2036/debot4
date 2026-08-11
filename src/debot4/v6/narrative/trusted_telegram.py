"""Trusted public-Telegram boundary for exact narrative source messages."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from ..telegram import TelegramPostObservation, TelegramPublicClient
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .actors import ActorRef
from .investigation_inputs import NarrativeEvent
from .source_receipts import VerifiedSourceReceipt, _TRUSTED_RECEIPT_ISSUER
from .trusted_events import events_from_verified_source
from .trusted_ingest import TrustedIngestError


class TelegramObservationFetcher(Protocol):
    def get_observation(
        self, channel: str, message_id: int
    ) -> TelegramPostObservation: ...


@dataclass(frozen=True, slots=True)
class VerifiedTelegramPost:
    receipt: VerifiedSourceReceipt
    actor: ActorRef

    @property
    def text(self) -> str:
        return self.receipt._content


@dataclass(slots=True)
class TelegramPostVerifier:
    fetcher: TelegramObservationFetcher = field(default_factory=TelegramPublicClient)
    registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY

    def verify(self, channel: str, message_id: int) -> VerifiedTelegramPost:
        observation = self.fetcher.get_observation(channel, message_id)
        post = observation.post
        expected_channel = channel.strip().lstrip("@").casefold()
        if post.channel != expected_channel or post.message_id != message_id:
            raise TrustedIngestError("Telegram message identity mismatch")
        actor = self.registry.resolve_telegram(post.channel)
        if actor is None:
            raise TrustedIngestError("Telegram channel is not registered")
        try:
            receipt = _TRUSTED_RECEIPT_ISSUER.telegram_message(
                channel=post.channel,
                message_id=post.message_id,
                content=post.text,
                published_at=post.created_at,
                fetched_at=post.fetched_at,
                raw_payload=observation.raw_payload,
                response_identity=observation.response_identity,
            )
        except ValueError as exc:
            raise TrustedIngestError(str(exc)) from None
        return VerifiedTelegramPost(receipt, actor)


def events_from_verified_telegram(
    post: VerifiedTelegramPost, narrative_key: str
) -> tuple[NarrativeEvent, ...]:
    return events_from_verified_source(post.actor, post.receipt, narrative_key)
