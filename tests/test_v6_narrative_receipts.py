from dataclasses import replace
from datetime import timedelta
from hashlib import sha256

import pytest

from debot4.v6.narrative import (
    ActorCapability,
    ActorRef,
    ActorTier,
    EndorsementScope,
    EvidenceProvider,
    NarrativeAction,
    NarrativeEvent,
    NarrativeVerdict,
    VerifiedSourceReceipt,
    investigate_narrative,
)
from debot4.v6.narrative.source_receipts import (
    _TRUSTED_RECEIPT_ISSUER,
    verify_source_receipt,
)
from debot4.v6.narrative.event_semantics import derive_event_semantics
from tests.test_v6_narrative_investigation import _active
from tests.v6_narrative_case import NOW, REGISTRY, complete_case


def _receipt(*, author_id: str, provider: EvidenceProvider = EvidenceProvider.X_GRAPHQL):
    content = "introducing example-narrative, this is great"
    raw = b'{"verified":"source bytes"}'
    return _TRUSTED_RECEIPT_ISSUER.x_status(
        provider=provider,
        status_id="1890071433214038103",
        author_id=author_id,
        author_handle="originator",
        content=content,
        published_at=NOW - timedelta(hours=2),
        fetched_at=NOW - timedelta(hours=2) + timedelta(seconds=1),
        raw_payload=raw,
        response_identity=f"test:{sha256(raw).hexdigest()}",
    )


def _source(actor: ActorRef, receipt) -> NarrativeEvent:
    derived = next(
        item for item in derive_event_semantics(actor, receipt, "example-narrative")
        if item.kind is complete_case().events[0].kind
    )
    return NarrativeEvent(
        derived.event_id,
        derived.kind,
        actor,
        derived.action,
        derived.endorsement,
        receipt,
        derived.claim,
        receipt.fetched_at,
    )


def test_receipt_cannot_be_freely_constructed_or_issued_from_grok() -> None:
    with pytest.raises(TypeError):
        VerifiedSourceReceipt()
    with pytest.raises(ValueError, match="direct X/FxTwitter"):
        _receipt(author_id="100109", provider=EvidenceProvider.GROK_CITATION)
    with pytest.raises(ValueError, match="direct X/FxTwitter"):
        _TRUSTED_RECEIPT_ISSUER.x_status(
            provider=EvidenceProvider.X_GRAPHQL,
            status_id="fabricated-status",
            author_id="100109",
            author_handle="originator",
            content="fake",
            published_at=NOW,
            fetched_at=NOW,
            raw_payload=b"fake",
            response_identity="fake",
        )


def test_receipt_seal_detects_field_and_raw_payload_tampering() -> None:
    receipt = _receipt(author_id="100109")
    assert verify_source_receipt(receipt)

    object.__setattr__(receipt, "canonical_url", "https://x.com/originator/status/999999")
    assert verify_source_receipt(receipt) is False


def test_registry_rejects_a_valid_receipt_with_the_wrong_stable_author_id() -> None:
    case = complete_case()
    wrong = _source(REGISTRY.resolve("originator"), _receipt(author_id="999999"))
    events = (wrong,) + case.events[1:]

    with pytest.raises(ValueError, match="untrusted actor/source receipt"):
        investigate_narrative(_active(events=events), actor_registry=REGISTRY)


def test_model_cannot_self_assign_a_registered_actor_profile() -> None:
    case = complete_case()
    receipt = case.events[0].receipt
    spoofed = ActorRef(
        "x:originator",
        "originator",
        ActorTier.GLOBAL_AGENDA,
        "model self-report",
        ("bsc",),
        (
            ActorCapability.ESTABLISH_ORIGIN,
            ActorCapability.CREATE_CATALYST,
            ActorCapability.BIND_CA,
        ),
    )
    events = (_source(spoofed, receipt),) + case.events[1:]

    with pytest.raises(ValueError, match="untrusted actor/source receipt"):
        investigate_narrative(_active(events=events), actor_registry=REGISTRY)


def test_receipt_and_registry_checks_preserve_the_real_complete_case() -> None:
    report = investigate_narrative(_active(), actor_registry=REGISTRY)

    assert report.verdict is NarrativeVerdict.BUY_CANDIDATE
    assert report.identity.startswith("v6.narrative_investigation.v1:")
