from datetime import datetime, timedelta, timezone

from debot4.v6.authority_wallet import AuthorityWalletAction, WalletAction
from debot4.v6.canonical_ca import (
    CaCandidate,
    CanonicalDecision,
    leader_change_event,
    resolve_canonical_ca,
)
from debot4.v6.distribution_access import (
    AccessObservation,
    AccessState,
    access_transition,
)
from debot4.v6.ownership_confirmation import (
    OwnershipObservation,
    OwnershipState,
    ownership_transition,
)
from debot4.v6.product_leak import PublicResourceSnapshot, product_diff_events
from debot4.v6.real_world_event import RealWorldObservation
from debot4.v6.risk_resolution import RiskObservation, RiskState, risk_transition


NOW = datetime(2026, 8, 12, 18, tzinfo=timezone.utc)
BEFORE = NOW - timedelta(seconds=2)
CA = "0x" + "1" * 40
OTHER_CA = "0x" + "2" * 40
WALLET = "0x" + "3" * 40
SOURCE = "https://example.com/evidence"
HASH = "a" * 64


def _ownership(state: OwnershipState, address: str = "") -> OwnershipObservation:
    return OwnershipObservation(
        "Bot", "2085838061347217408", "original_creator", state,
        NOW, NOW, SOURCE, HASH, "bsc", address,
    )


def test_creator_ca_binding_is_evidence_only() -> None:
    event = ownership_transition(
        _ownership(OwnershipState.ACKNOWLEDGED),
        _ownership(OwnershipState.CA_BOUND, CA),
    )

    assert event is not None
    assert event.subtype == "acknowledged_to_ca_bound"
    assert event.token_address == CA
    assert event.buy_eligible is False


def test_authority_wallet_receipt_keeps_transaction_identity() -> None:
    event = AuthorityWalletAction(
        "bsc", CA, WALLET, "creator_wallet", WalletAction.FIRST_BUY,
        "0x" + "4" * 64, 123, 7, NOW, NOW, SOURCE, HASH,
    ).event()

    assert event.current["block_number"] == 123
    assert event.current["log_index"] == 7
    assert event.buy_eligible is False


def test_product_diff_emits_each_new_term_and_exact_ca() -> None:
    old = PublicResourceSnapshot(
        "xai-docs", "xai", "official_company", BEFORE, SOURCE, HASH,
        frozenset({"grok"}),
    )
    new = PublicResourceSnapshot(
        "xai-docs", "xai", "official_company", NOW, SOURCE, "b" * 64,
        frozenset({"grok", "bot"}), frozenset({CA}),
    )

    events = product_diff_events(old, new)

    assert {item.subtype for item in events} == {"public_term_added", "public_ca_added"}
    assert next(item for item in events if item.subtype == "public_ca_added").token_address == CA


def test_real_world_event_cannot_become_a_buy_instruction() -> None:
    event = RealWorldObservation(
        "new mascot", "new_character_named", "publisher", "primary_source",
        BEFORE, NOW, SOURCE, HASH,
    ).event()

    assert event.current["research_candidate"] is True
    assert event.token_address == ""
    assert event.buy_eligible is False


def test_distribution_tracks_actual_open_after_announcement() -> None:
    announced = AccessObservation(
        "exchange", "BOT/USDT", "exchange", "official_venue",
        AccessState.ANNOUNCED, BEFORE, BEFORE, SOURCE, HASH, "bsc", CA,
    )
    opened = AccessObservation(
        "exchange", "BOT/USDT", "exchange", "official_venue",
        AccessState.TRADING_OPEN, NOW, NOW, SOURCE, "b" * 64, "bsc", CA,
    )

    event = access_transition(announced, opened)

    assert event is not None
    assert event.previous["state"] == "announced"
    assert event.current["state"] == "trading_open"


def test_risk_resolution_retains_the_prior_denial() -> None:
    denied = RiskObservation(
        "Bot", "creator", "original_creator", RiskState.DENIED,
        "not affiliated", BEFORE, BEFORE, SOURCE, HASH, "bsc", CA,
    )
    resolved = RiskObservation(
        "Bot", "creator", "original_creator", RiskState.RESOLVED,
        "creator accepted control", NOW, NOW, SOURCE, "b" * 64, "bsc", CA,
    )

    event = risk_transition(denied, resolved)

    assert event is not None
    assert event.subtype == "risk_resolved"
    assert event.previous["reason"] == "not affiliated"


def test_canonical_ca_requires_a_unique_official_binding() -> None:
    unresolved = resolve_canonical_ca((
        CaCandidate(CA, authority_wallet=True),
        CaCandidate(OTHER_CA, holder_migration=True),
    ))
    resolved = resolve_canonical_ca((
        CaCandidate(CA, official_post=True, creator_wallet=True),
        CaCandidate(OTHER_CA, holder_migration=True),
    ))

    event = leader_change_event(
        CanonicalDecision("unresolved", "", unresolved.scores), resolved,
        subject="Bot", actor_id="bot", actor_role="official_product",
        occurred_at=NOW, first_seen_at=NOW, source_url=SOURCE,
        evidence_hash=HASH, chain="bsc",
    )

    assert unresolved.status == "unresolved"
    assert resolved.leader == CA
    assert event is not None and event.token_address == CA
    assert event.buy_eligible is False
