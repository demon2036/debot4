from datetime import datetime, timedelta, timezone

import pytest

from debot4.v6.narrative import (
    ActorCapability,
    ActorRef,
    ActorRegistration,
    ActorRegistry,
    ActorTier,
    DiscoveryMode,
    EndorsementScope,
    FxTwitterObservation,
    FxTwitterTweet,
    InvestigationRequest,
    NarrativeAction,
    NarrativeEvent,
    NarrativeEventKind,
    TrustedIngestError,
    XStatusVerifier,
    events_from_verified_status,
    investigate_narrative,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
STATUS_ID = "1890071433214038103"
AUTHOR_ID = "902926941413453824"
URL = f"https://x.com/cz_binance/status/{STATUS_ID}"
CA = "0x1111111111111111111111111111111111111111"


class FakeFetcher:
    def __init__(self, observation: FxTwitterObservation) -> None:
        self.observation = observation

    def fetch_observation(self, status_url: str) -> FxTwitterObservation:
        assert status_url == URL
        return self.observation


def _registry(*capabilities: ActorCapability) -> ActorRegistry:
    actor = ActorRef(
        "x:cz_binance",
        "cz_binance",
        ActorTier.ECOSYSTEM_AUTHORITY,
        "test-reviewed stable X identity",
        ("bsc", "bnb"),
        capabilities,
    )
    registration = ActorRegistration(
        actor,
        ("https://x.com/cz_binance/status/",),
        (AUTHOR_ID,),
    )
    return ActorRegistry((registration,))


def _observation(text: str, *, handle: str = "cz_binance") -> FxTwitterObservation:
    tweet = FxTwitterTweet(
        STATUS_ID,
        handle,
        AUTHOR_ID,
        text,
        NOW - timedelta(minutes=2),
        NOW,
        f"https://x.com/{handle}/status/{STATUS_ID}",
    )
    raw = ("provider:" + text).encode()
    return FxTwitterObservation(tweet, raw, "cf-ray:test-response")


def test_verified_post_without_ca_is_source_and_catalyst_only() -> None:
    registry = _registry(
        ActorCapability.ESTABLISH_ORIGIN,
        ActorCapability.CREATE_CATALYST,
    )
    status = XStatusVerifier(
        FakeFetcher(_observation("Broccoli's Story: meet my dog Broccoli.")),
        registry,
    ).verify(URL)

    events = events_from_verified_status(status, "Broccoli")

    assert {item.kind for item in events} == {
        NarrativeEventKind.SOURCE_EVENT,
        NarrativeEventKind.CURRENT_CATALYST,
    }
    assert all(not item.exact_ca and not item.token_address for item in events)


def test_unknown_verified_exact_ca_is_community_evidence_not_official_binding() -> None:
    observation = _observation(f"Community Broccoli launch {CA}")
    status = XStatusVerifier(
        FakeFetcher(observation),
        ActorRegistry(()),
    ).verify(URL)

    events = events_from_verified_status(status, "Broccoli")

    assert {item.kind for item in events} == {NarrativeEventKind.PROPAGATION}
    assert all(not item.token_address and not item.exact_ca for item in events)


def test_mismatched_provider_author_is_rejected_before_event_creation() -> None:
    verifier = XStatusVerifier(
        FakeFetcher(_observation("Broccoli", handle="not_cz")),
        _registry(ActorCapability.CREATE_CATALYST),
    )

    with pytest.raises(TrustedIngestError, match="handle mismatch"):
        verifier.verify(URL)


def test_genuine_receipt_cannot_be_relabelled_into_a_fake_buy_event() -> None:
    registry = _registry(
        ActorCapability.ESTABLISH_ORIGIN,
        ActorCapability.CREATE_CATALYST,
    )
    status = XStatusVerifier(
        FakeFetcher(_observation("Broccoli's Story: no contract address.")),
        registry,
    ).verify(URL)
    forged = NarrativeEvent(
        "forged-binding",
        NarrativeEventKind.TOKEN_BINDING,
        status.actor,
        NarrativeAction.EXACT_CA_CLAIM,
        EndorsementScope.TOKEN_EXPLICIT,
        status.receipt,
        "caller self-labelled a binding",
        NOW,
        CA,
        True,
    )
    request = InvestigationRequest(
        DiscoveryMode.ACTIVE_ACTOR,
        "trigger-1",
        "Broccoli",
        NOW,
        (forged,),
        (),
        trigger_event_id=forged.event_id,
    )

    with pytest.raises(ValueError, match="not derived from verified content"):
        investigate_narrative(request, actor_registry=registry)
