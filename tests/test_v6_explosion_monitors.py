from datetime import datetime, timedelta, timezone
import json

from debot4.v6.authority_wallet import (
    AuthorityWalletAction,
    AuthorityWalletMonitor,
    WalletAction,
)
from debot4.v6.canonical_ca import CaCandidate, CanonicalCaMonitor
from debot4.v6.distribution_access import (
    AccessObservation,
    AccessState,
    DistributionAccessMonitor,
)
from debot4.v6.explosion import ExplosionEventStore, JsonEvidenceStateStore
from debot4.v6.ownership_confirmation import (
    OwnershipConfirmationMonitor,
    OwnershipObservation,
    OwnershipState,
)
from debot4.v6.real_world_event import RealWorldEventMonitor, RealWorldObservation
from debot4.v6.risk_resolution import (
    RiskObservation,
    RiskResolutionMonitor,
    RiskState,
)


NOW = datetime(2026, 8, 12, 18, tzinfo=timezone.utc)
BEFORE = NOW - timedelta(seconds=2)
SOURCE = "https://example.com/evidence"
HASH = "a" * 64
NEW_HASH = "b" * 64
CA = "0x" + "1" * 40
OTHER_CA = "0x" + "2" * 40
WALLET = "0x" + "3" * 40


def _state(tmp_path, name: str) -> JsonEvidenceStateStore:
    return JsonEvidenceStateStore(tmp_path / f"{name}.json", namespace=name)


def test_state_store_is_private_atomic_and_reload_safe(tmp_path) -> None:
    path = tmp_path / "state.json"
    first = JsonEvidenceStateStore(path, namespace="test")
    second = JsonEvidenceStateStore(path, namespace="test")

    first.save("A", {"state": "one"})
    second.save("B", {"state": "two"})

    assert first.load("b") == {"state": "two"}
    assert first.count() == 2
    assert path.stat().st_mode & 0o777 == 0o600
    assert json.loads(path.read_text())["namespace"] == "test"


def test_ownership_transition_survives_monitor_restart(tmp_path) -> None:
    state_path = tmp_path / "ownership.json"
    event_path = tmp_path / "events.sqlite3"
    denied = OwnershipObservation(
        "Bot", "creator", "original_creator", OwnershipState.DENIED,
        BEFORE, BEFORE, SOURCE, HASH, "bsc",
    )
    bound = OwnershipObservation(
        "Bot", "creator", "original_creator", OwnershipState.CA_BOUND,
        NOW, NOW, SOURCE, NEW_HASH, "bsc", CA,
    )

    with ExplosionEventStore(event_path) as events:
        first = OwnershipConfirmationMonitor(
            JsonEvidenceStateStore(state_path, namespace="ownership"), events,
        )
        assert first.observe(denied) is None
    with ExplosionEventStore(event_path) as events:
        second = OwnershipConfirmationMonitor(
            JsonEvidenceStateStore(state_path, namespace="ownership"), events,
        )
        event = second.observe(bound)
        assert event is not None and event.token_address == CA
        assert events.count() == 1


def test_distribution_and_risk_transitions_are_persisted(tmp_path) -> None:
    with ExplosionEventStore(tmp_path / "events.sqlite3") as events:
        access = DistributionAccessMonitor(_state(tmp_path, "access"), events)
        risk = RiskResolutionMonitor(_state(tmp_path, "risk"), events)
        assert access.observe(AccessObservation(
            "exchange", "BOT/USDT", "venue", "official_venue",
            AccessState.ANNOUNCED, BEFORE, BEFORE, SOURCE, HASH, "bsc", CA,
        )) is None
        opened = access.observe(AccessObservation(
            "exchange", "BOT/USDT", "venue", "official_venue",
            AccessState.TRADING_OPEN, NOW, NOW, SOURCE, NEW_HASH, "bsc", CA,
        ))
        assert risk.observe(RiskObservation(
            "Bot", "creator", "original_creator", RiskState.DENIED,
            "not affiliated", BEFORE, BEFORE, SOURCE, HASH, "bsc", CA,
        )) is None
        resolved = risk.observe(RiskObservation(
            "Bot", "creator", "original_creator", RiskState.RESOLVED,
            "accepted control", NOW, NOW, SOURCE, NEW_HASH, "bsc", CA,
        ))

        assert opened is not None and opened.subtype == "distribution_opened"
        assert resolved is not None and resolved.subtype == "risk_resolved"
        assert events.count() == 2


def test_receipt_and_real_world_ingestion_are_idempotent(tmp_path) -> None:
    action = AuthorityWalletAction(
        "bsc", CA, WALLET, "creator_wallet", WalletAction.FIRST_BUY,
        "0x" + "4" * 64, 123, 7, NOW, NOW, SOURCE, HASH,
    )
    observation = RealWorldObservation(
        "new mascot", "new_character_named", "publisher", "primary_source",
        NOW, NOW, SOURCE, NEW_HASH,
    )
    with ExplosionEventStore(tmp_path / "events.sqlite3") as events:
        wallets = AuthorityWalletMonitor(events)
        reality = RealWorldEventMonitor(events)
        assert wallets.ingest(action) is not None
        assert wallets.ingest(action) is None
        assert reality.ingest(observation) is not None
        assert reality.ingest(observation) is None
        assert events.count() == 2


def test_canonical_ca_emits_only_new_official_selection(tmp_path) -> None:
    with ExplosionEventStore(tmp_path / "events.sqlite3") as events:
        monitor = CanonicalCaMonitor(_state(tmp_path, "canonical"), events)
        evidence = dict(
            subject="Bot", actor_id="bot", actor_role="official_product",
            occurred_at=NOW, first_seen_at=NOW, source_url=SOURCE,
            evidence_hash=HASH, chain="bsc",
        )
        assert monitor.evaluate((
            CaCandidate(CA, authority_wallet=True),
            CaCandidate(OTHER_CA, holder_migration=True),
        ), **evidence) is None
        selected = monitor.evaluate((
            CaCandidate(CA, official_post=True),
            CaCandidate(OTHER_CA, holder_migration=True),
        ), **{**evidence, "evidence_hash": NEW_HASH})
        repeated = monitor.evaluate((
            CaCandidate(CA, official_post=True),
            CaCandidate(OTHER_CA, holder_migration=True),
        ), **{**evidence, "evidence_hash": NEW_HASH})

        assert selected is not None and selected.token_address == CA
        assert repeated is None
        assert events.count() == 1
