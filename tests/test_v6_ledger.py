from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import sqlite3
import pytest
from debot4.v6.ledger import (
    OFFICIAL_KOL_SOURCE,
    RANKS_KOL_SOURCE,
    V6Ledger,
    V6LedgerConflict,
    V6LedgerFinalized,
)
UTC = timezone.utc
START = datetime(2026, 8, 1, tzinfo=UTC)
TOKEN = "0x" + "ab" * 20
SOURCE = "v6:test"
URI = "evidence://test"
def moment(*, seconds: int = 0, minutes: int = 0) -> datetime:
    return START + timedelta(seconds=seconds, minutes=minutes)
def block_hash(number: int) -> str:
    return "0x" + f"{number:064x}"
@dataclass
class Clock:
    value: datetime = START

    def __call__(self) -> datetime:
        return self.value
@pytest.fixture
def env(tmp_path):
    clock = Clock()
    ledger = V6Ledger(tmp_path / "v6.sqlite3", clock=clock)
    try:
        yield ledger, clock
    finally:
        ledger.close()
def seed_signal(ledger: V6Ledger, clock: Clock):
    clock.value = max(clock.value, moment(seconds=10))
    return ledger.record_candidate_with_signal(
        candidate_id="candidate-1", chain="BSC", token_address=TOKEN.upper(),
        detected_at=moment(seconds=1), candidate_available_at=moment(seconds=5),
        signal_id="signal-1", signal_event_at=moment(seconds=8),
        signal_available_at=moment(seconds=10), signal_kind="official_post",
        source=SOURCE, evidence_uri=URI, candidate_metadata={"b": 2, "a": 1},
        signal_metadata={"rank": 1},
    )
def commit_buy(
    ledger: V6Ledger, clock: Clock, *, buy_id: str = "buy-1",
    decision_id: str = "decision-1", entry_block: int = 100,
):
    clock.value = max(clock.value, moment(seconds=12))
    return ledger.commit_simulated_buy(
        buy_id=buy_id, decision_id=decision_id, candidate_id="candidate-1",
        signal_id="signal-1", decided_at=moment(seconds=11),
        executed_at=moment(seconds=12), reason="historical KOL supports entry",
        strategy_version="v6.0", block_number=entry_block,
        block_hash=block_hash(entry_block),
        parent_block_hash=block_hash(entry_block - 1), entry_fdv_usd="1000",
        notional_usd="10", entry_position_value_usd="10", source=SOURCE,
        evidence_uri=URI, metadata={"paper": True},
    )
def add_canonical(
    ledger: V6Ledger, clock: Clock, *, buy_id: str, block: int,
    hash_number: int, parent_hash_number: int, at: datetime,
    fdv: str, value: str, sighted_at: datetime | None = None,
):
    sighted = sighted_at or at
    clock.value = max(clock.value, sighted)
    return ledger.commit_canonical_observation(
        buy_id=buy_id, block_number=block, block_hash=block_hash(hash_number),
        parent_hash=block_hash(parent_hash_number), observed_at=at,
        available_at=at, fdv_usd=fdv, position_value_usd=value,
        sighted_at=sighted, head_available_at=sighted, source=SOURCE,
        evidence_uri=URI,
    )
def finalize(ledger: V6Ledger, buy_id: str, cutoff: datetime, **kwargs: object):
    return ledger.finalize_one_hour(
        buy_id, as_of=cutoff,
        coverage_complete_through=moment(seconds=12) + timedelta(hours=1),
        **kwargs,
    )
def test_candidate_signal_bundle_is_atomic_monotonic_and_as_of(env):
    ledger, clock = env
    first = seed_signal(ledger, clock)
    assert first.candidate.record.commit_seq == first.signal.record.commit_seq
    assert first.candidate.record.inserted_at == first.signal.record.inserted_at
    assert first.candidate.record.token_address == TOKEN
    assert first.candidate.record.metadata_json == '{"a":1,"b":2}'
    clock.value = moment(seconds=11)
    replay = seed_signal(ledger, clock)
    assert not replay.candidate.inserted and not replay.signal.inserted
    clock.value = moment(seconds=20)
    ledger.record_current_signal(
        signal_id="signal-2", candidate_id="candidate-1",
        event_at=moment(seconds=19), available_at=moment(seconds=20),
        signal_kind="official_post", source=SOURCE, evidence_uri=URI,
    )
    clock.value = moment(seconds=30)
    ledger.record_current_signal(
        signal_id="late-backfill", candidate_id="candidate-1",
        event_at=moment(seconds=25), available_at=moment(seconds=25),
        signal_kind="official_post", source=SOURCE, evidence_uri=URI,
    )
    assert ledger.current_signal("candidate-1", as_of=moment(seconds=26)).signal_id == "signal-2"
    assert ledger.current_signal("candidate-1", as_of=clock.value).signal_id == "late-backfill"
    with pytest.raises(V6LedgerConflict):
        ledger.record_candidate_with_signal(
            candidate_id="rolled-back", chain="bsc", token_address=TOKEN,
            detected_at=moment(seconds=29), candidate_available_at=clock.value,
            signal_id="signal-1", signal_event_at=clock.value,
            signal_available_at=clock.value, signal_kind="other",
            source=SOURCE, evidence_uri=URI,
        )
    assert ledger.candidate("rolled-back") is None
def test_kol_allowlist_sequence_boundary_and_ranks_annotations(env):
    ledger, clock = env
    clock.value = moment(seconds=3)
    good = ledger.record_kol_evidence(
        evidence_id="good", chain="bsc", token_address=TOKEN,
        signal_id="older", event_at=moment(), available_at=moment(seconds=1),
        qualified_at=moment(seconds=2), source=OFFICIAL_KOL_SOURCE,
        evidence_uri=URI,
    )
    ranks = ledger.record_kol_evidence(
        evidence_id="ranks", chain="bsc", token_address=TOKEN,
        signal_id="ranks-old", event_at=moment(), available_at=moment(seconds=1),
        qualified_at=moment(seconds=2), source=RANKS_KOL_SOURCE,
        evidence_uri=URI, metadata={"increase": 2},
    )
    ledger.record_kol_evidence(
        evidence_id="same", chain="bsc", token_address=TOKEN,
        signal_id="signal-1", event_at=moment(), available_at=moment(seconds=1),
        qualified_at=moment(seconds=2), evidence_uri=URI,
    )
    current = seed_signal(ledger, clock).signal.record
    clock.value = moment(seconds=4)  # deliberate wall-clock rollback
    late = ledger.record_kol_evidence(
        evidence_id="late", chain="bsc", token_address=TOKEN,
        signal_id="old-but-late", event_at=moment(),
        available_at=moment(seconds=1), qualified_at=moment(seconds=2),
        source=RANKS_KOL_SOURCE, evidence_uri=URI,
    )
    assert late.record.commit_seq > current.commit_seq
    assert ranks.record.metadata["evidence_semantics"] == "provider_aggregate_proxy"
    assert ranks.record.metadata["chain_verified"] is False
    assert ranks.record.metadata["wallet_buy_claim"] is False
    clock.value = moment(seconds=12)
    eligible = ledger.eligible_historical_kol(current_signal_id="signal-1", as_of=clock.value)
    assert {item.evidence_id for item in eligible} == {good.record.evidence_id, "ranks"}
    assert ledger.record_entry_decision(
        decision_id="accepted", candidate_id="candidate-1", signal_id="signal-1",
        kol_evidence_id="ranks", decided_at=clock.value, status="buy",
        reason="eligible ranks proxy", source=SOURCE, strategy_version="v6.0",
    ).inserted
    with pytest.raises(ValueError, match="not historical"):
        ledger.record_entry_decision(
            decision_id="rejected", candidate_id="candidate-1",
            signal_id="signal-1", kol_evidence_id="late", decided_at=clock.value,
            status="buy", reason="late", source=SOURCE, strategy_version="v6.0",
        )
    with pytest.raises(ValueError, match="chain_verified"):
        ledger.record_kol_evidence(
            evidence_id="lying", chain="bsc", token_address=TOKEN,
            signal_id="old", event_at=moment(), available_at=moment(seconds=1),
            qualified_at=moment(seconds=2), source=RANKS_KOL_SOURCE,
            evidence_uri=URI, metadata={"chain_verified": True},
        )
def test_buy_bundle_is_atomic_idempotent_and_shares_commit(env):
    ledger, clock = env
    seed_signal(ledger, clock)
    first = commit_buy(ledger, clock)
    seqs = {first.decision.record.commit_seq, first.buy.record.commit_seq,
            first.entry.observation.record.commit_seq,
            first.entry.head_sighting.record.commit_seq}
    assert len(seqs) == 1 and first.buy.record.notional_usd == Decimal("10")
    clock.value = moment(seconds=13)
    replay = commit_buy(ledger, clock)
    assert not replay.decision.inserted and not replay.buy.inserted
    assert not replay.entry.observation.inserted and not replay.entry.head_sighting.inserted
    with pytest.raises(V6LedgerConflict):
        commit_buy(ledger, clock, buy_id="buy-1", decision_id="rolled-back")
    assert ledger.entry_decision("rolled-back") is None
def test_canonical_sightings_support_a_b_a_without_fork_stitching(env):
    ledger, clock = env
    seed_signal(ledger, clock)
    commit_buy(ledger, clock)
    add_canonical(ledger, clock, buy_id="buy-1", block=101, hash_number=101,
                  parent_hash_number=100, at=moment(seconds=20), fdv="1200", value="12")
    add_canonical(ledger, clock, buy_id="buy-1", block=102, hash_number=102,
                  parent_hash_number=101, at=moment(seconds=30), fdv="1300", value="13")
    add_canonical(ledger, clock, buy_id="buy-1", block=101, hash_number=901,
                  parent_hash_number=100, at=moment(seconds=21), fdv="900", value="9",
                  sighted_at=moment(seconds=31))
    add_canonical(ledger, clock, buy_id="buy-1", block=102, hash_number=902,
                  parent_hash_number=901, at=moment(seconds=22), fdv="800", value="8",
                  sighted_at=moment(seconds=32))
    clock.value = moment(seconds=33)
    ledger.record_head_sighting(
        buy_id="buy-1", block_number=102, block_hash=block_hash(102),
        sighted_at=clock.value, available_at=clock.value, source=SOURCE, evidence_uri=URI,
    )
    with pytest.raises(sqlite3.IntegrityError, match="hash identity"):
        ledger._connection.execute(
            "INSERT OR REPLACE INTO v6_block_observations "
            "SELECT 'replacement',buy_id,block_number,block_hash,parent_hash,"
            "observed_at_us,available_at_us,fdv_usd,position_value_usd,source,"
            "evidence_uri,metadata_json,commit_seq,inserted_at_us "
            "FROM v6_block_observations WHERE block_hash=?", (block_hash(101),),
        )
    clock.value = moment(seconds=12) + timedelta(hours=1)
    outcome = finalize(ledger, "buy-1", clock.value,
                       max_allowed_gap=timedelta(hours=1)).record
    assert outcome.status == "complete" and outcome.final_fdv_usd == Decimal("1300")
    assert outcome.final_block_number == 102 and outcome.observation_count == 2
    with pytest.raises(V6LedgerFinalized):
        add_canonical(ledger, clock, buy_id="buy-1", block=103, hash_number=103,
                      parent_hash_number=102, at=moment(seconds=40), fdv="1400", value="14")
    with pytest.raises(sqlite3.IntegrityError, match="finalized"):
        ledger._connection.execute(
            "INSERT INTO v6_block_observations "
            "SELECT 'post-seal',buy_id,block_number+1,?,block_hash,observed_at_us+1,"
            "available_at_us+1,fdv_usd,position_value_usd,source,evidence_uri,"
            "metadata_json,commit_seq,inserted_at_us FROM v6_block_observations "
            "WHERE buy_id='buy-1' LIMIT 1", (block_hash(9999),),
        )
def test_complete_outcome_requires_lateness_watermark_and_retries_frozen(env):
    ledger, clock = env
    seed_signal(ledger, clock)
    commit_buy(ledger, clock)
    entry = moment(seconds=12)
    for block, minutes, fdv, value in (
        (101, 20, "1500", "15"), (102, 40, "2500", "25"), (103, 60, "1200", "12")
    ):
        add_canonical(ledger, clock, buy_id="buy-1", block=block, hash_number=block,
                      parent_hash_number=block - 1, at=entry + timedelta(minutes=minutes),
                      fdv=fdv, value=value)
    clock.value = entry + timedelta(hours=1)
    with pytest.raises(ValueError, match="lateness"):
        finalize(ledger, "buy-1", clock.value, allowed_lateness=timedelta(minutes=1))
    clock.value += timedelta(minutes=1)
    result = finalize(ledger, "buy-1", clock.value,
                      allowed_lateness=timedelta(minutes=1),
                      max_allowed_gap=timedelta(minutes=20)).record
    assert result.status == "complete" and result.max_gap == timedelta(minutes=20)
    assert (result.peak_fdv_usd, result.final_fdv_usd) == (Decimal("2500"), Decimal("1200"))
    assert (result.peak_multiple, result.final_multiple) == (Decimal("2.5"), Decimal("1.2"))
    clock.value += timedelta(minutes=1)
    replay = finalize(ledger, "buy-1", clock.value, allowed_lateness=timedelta(0))
    assert not replay.inserted and replay.record.cutoff_at == result.cutoff_at
    commit_buy(ledger, clock, buy_id="late-recorded", decision_id="late-decision",
               entry_block=300)
    with pytest.raises(ValueError, match="causally visible"):
        finalize(ledger, "late-recorded", entry + timedelta(hours=1))
def test_incomplete_and_entry_reorg_results_are_null_and_immutable(env):
    ledger, clock = env
    seed_signal(ledger, clock)
    commit_buy(ledger, clock, buy_id="empty", decision_id="decision-a")
    commit_buy(ledger, clock, buy_id="gap", decision_id="decision-b", entry_block=200)
    commit_buy(ledger, clock, buy_id="reorg", decision_id="decision-c", entry_block=300)
    entry = moment(seconds=12)
    add_canonical(ledger, clock, buy_id="gap", block=201, hash_number=201,
                  parent_hash_number=200, at=entry + timedelta(minutes=10),
                  fdv="1100", value="11")
    add_canonical(ledger, clock, buy_id="reorg", block=300, hash_number=999,
                  parent_hash_number=299, at=entry, fdv="900", value="9",
                  sighted_at=moment(seconds=20))
    clock.value = entry + timedelta(hours=1)
    with pytest.raises(ValueError, match="watermark"):
        ledger.finalize_one_hour(
            "empty", as_of=clock.value,
            coverage_complete_through=clock.value - timedelta(microseconds=1),
        )
    empty = finalize(ledger, "empty", clock.value,
                     max_allowed_gap=timedelta(hours=1)).record
    gap = finalize(ledger, "gap", clock.value,
                   max_allowed_gap=timedelta(minutes=20)).record
    reorg = finalize(ledger, "reorg", clock.value,
                     max_allowed_gap=timedelta(hours=1)).record
    assert (empty.status, empty.reason) == ("incomplete", "no_post_entry_observation")
    assert (gap.status, gap.reason) == ("incomplete", "coverage_gap_exceeded")
    assert (reorg.status, reorg.reason) == ("invalidated", "entry_block_reorged")
    for record in (empty, gap, reorg):
        assert record.peak_fdv_usd is None and record.final_fdv_usd is None
        assert record.peak_multiple is None and record.final_pnl_usd is None
    with pytest.raises(sqlite3.IntegrityError, match="UPDATE is forbidden"):
        ledger._connection.execute(
            "UPDATE v6_candidates SET source='changed' WHERE candidate_id='candidate-1'"
        )
