"""Convert sealed source receipts into deterministic narrative events."""

from __future__ import annotations

from .actors import ActorRef
from .event_semantics import derive_event_semantics
from .investigation_inputs import NarrativeEvent
from .source_receipts import VerifiedSourceReceipt


def events_from_verified_source(
    actor: ActorRef,
    receipt: VerifiedSourceReceipt,
    narrative_key: str,
) -> tuple[NarrativeEvent, ...]:
    """The sole receipt-to-event conversion path for trusted adapters."""

    return tuple(
        NarrativeEvent(
            event_id=item.event_id,
            kind=item.kind,
            actor=actor,
            action=item.action,
            endorsement=item.endorsement,
            receipt=receipt,
            claim=item.claim,
            first_seen_at=receipt.fetched_at,
            token_address=item.token_address,
            exact_ca=item.exact_ca,
        )
        for item in derive_event_semantics(actor, receipt, narrative_key)
    )
