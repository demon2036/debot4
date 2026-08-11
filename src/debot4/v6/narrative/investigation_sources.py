"""Reject unregistered actors and semantically impossible source claims."""

from __future__ import annotations

from .actor_registry import ActorRegistry
from .event_semantics import derive_event_semantics
from .investigation_domain import (
    EndorsementScope,
    NarrativeAction,
    NarrativeEventKind,
)
from .investigation_inputs import NarrativeEvent
from .source_receipts import verify_source_receipt


_SOURCE_ACTIONS = {
    NarrativeAction.ORIGINATE,
    NarrativeAction.ANNOUNCE,
    NarrativeAction.LAUNCH,
    NarrativeAction.RELEASE,
}
_BINDING_ACTIONS = {
    NarrativeAction.EXACT_CA_CLAIM,
    NarrativeAction.ANNOUNCE,
    NarrativeAction.LAUNCH,
    NarrativeAction.RELEASE,
}
_CATALYST_ACTIONS = _SOURCE_ACTIONS | {
    NarrativeAction.REPLY,
    NarrativeAction.REPOST,
    NarrativeAction.QUOTE,
    NarrativeAction.REPORT,
    NarrativeAction.MENTION,
}
_PROPAGATION_ACTIONS = {
    NarrativeAction.REPLY,
    NarrativeAction.REPOST,
    NarrativeAction.QUOTE,
    NarrativeAction.REPORT,
    NarrativeAction.MENTION,
}
_POSITIVE = {
    EndorsementScope.TOKEN_EXPLICIT,
    EndorsementScope.NARRATIVE_POSITIVE,
    EndorsementScope.NARRATIVE_NEUTRAL,
}


def validate_event_sources(
    events: tuple[NarrativeEvent, ...],
    registry: ActorRegistry,
    narrative_key: str,
) -> None:
    for event in events:
        if not verify_source_receipt(event.receipt) or not registry.permits(
            event.actor,
            event.receipt.author_handle,
            event.receipt.author_id,
            event.source_url,
            narrative_key,
        ):
            raise ValueError(f"untrusted actor/source receipt: {event.event_id}")
        _validate_derived_semantics(event, narrative_key)
        _validate_semantics(event)


def _validate_derived_semantics(event: NarrativeEvent, narrative_key: str) -> None:
    allowed = derive_event_semantics(event.actor, event.receipt, narrative_key)
    actual = (
        event.event_id,
        event.kind,
        event.action,
        event.endorsement,
        event.claim,
        event.token_address,
        event.exact_ca,
    )
    expected = {
        (
            item.event_id, item.kind, item.action, item.endorsement,
            item.claim, item.token_address, item.exact_ca,
        )
        for item in allowed
    }
    if actual not in expected or event.first_seen_at != event.receipt.fetched_at:
        raise ValueError(f"event was not derived from verified content: {event.event_id}")


def _validate_semantics(event: NarrativeEvent) -> None:
    kind = event.kind
    if kind is NarrativeEventKind.SOURCE_EVENT:
        _require(event, event.action in _SOURCE_ACTIONS and event.endorsement in _POSITIVE)
    elif kind is NarrativeEventKind.TOKEN_CREATED:
        _require(event, event.action in {NarrativeAction.LAUNCH, NarrativeAction.RELEASE})
    elif kind is NarrativeEventKind.TOKEN_BINDING:
        _require(event, (
            event.action in _BINDING_ACTIONS
            and event.endorsement is EndorsementScope.TOKEN_EXPLICIT
            and event.exact_ca
        ))
    elif kind is NarrativeEventKind.CURRENT_CATALYST:
        _require(event, event.action in _CATALYST_ACTIONS and event.endorsement in _POSITIVE)
    elif kind is NarrativeEventKind.PROPAGATION:
        _require(event, event.action in _PROPAGATION_ACTIONS and event.endorsement in _POSITIVE)
    elif kind is NarrativeEventKind.COUNTER_EVIDENCE:
        _require(event, (
            event.action is NarrativeAction.DENY
            or event.endorsement is EndorsementScope.NEGATIVE
        ))


def _require(event: NarrativeEvent, condition: bool) -> None:
    if not condition:
        raise ValueError(f"event semantics contradict kind: {event.event_id}")
