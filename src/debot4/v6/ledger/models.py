"""Immutable public records returned by the v6 ledger."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generic, TypeVar
import json

from .codec import ONE_HOUR


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class InsertResult(Generic[T]):
    record: T
    inserted: bool


class _MetadataRecord:
    metadata_json: str

    @property
    def metadata(self) -> dict[str, object]:
        return json.loads(self.metadata_json)


@dataclass(frozen=True, slots=True)
class Candidate(_MetadataRecord):
    candidate_id: str
    chain: str
    token_address: str
    detected_at: datetime
    available_at: datetime
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class CurrentSignal(_MetadataRecord):
    signal_id: str
    candidate_id: str
    chain: str
    token_address: str
    event_at: datetime
    available_at: datetime
    signal_kind: str
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class HistoricalKolEvidence(_MetadataRecord):
    evidence_id: str
    chain: str
    token_address: str
    signal_id: str
    event_at: datetime
    available_at: datetime
    qualified_at: datetime
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class EntryDecision(_MetadataRecord):
    decision_id: str
    candidate_id: str
    signal_id: str
    kol_evidence_id: str | None
    decided_at: datetime
    status: str
    reason: str
    source: str
    strategy_version: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class SimulatedBuy(_MetadataRecord):
    buy_id: str
    decision_id: str
    candidate_id: str
    signal_id: str
    chain: str
    token_address: str
    executed_at: datetime
    block_number: int
    block_hash: str
    entry_fdv_usd: Decimal
    notional_usd: Decimal
    entry_position_value_usd: Decimal
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime

    @property
    def window_ends_at(self) -> datetime:
        return self.executed_at + ONE_HOUR


@dataclass(frozen=True, slots=True)
class BlockObservation(_MetadataRecord):
    observation_id: str
    buy_id: str
    block_number: int
    block_hash: str
    parent_hash: str
    observed_at: datetime
    available_at: datetime
    fdv_usd: Decimal
    position_value_usd: Decimal
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class CanonicalHeadSighting(_MetadataRecord):
    sighting_id: str
    buy_id: str
    block_number: int
    block_hash: str
    sighted_at: datetime
    available_at: datetime
    source: str
    evidence_uri: str
    metadata_json: str
    commit_seq: int
    inserted_at: datetime


@dataclass(frozen=True, slots=True)
class OneHourResult:
    buy_id: str
    status: str
    reason: str | None
    window_ends_at: datetime
    cutoff_at: datetime
    coverage_complete_through: datetime
    allowed_lateness: timedelta
    observation_count: int
    max_gap: timedelta
    max_allowed_gap: timedelta
    peak_fdv_usd: Decimal | None
    peak_position_value_usd: Decimal | None
    peak_observed_at: datetime | None
    peak_block_number: int | None
    final_fdv_usd: Decimal | None
    final_position_value_usd: Decimal | None
    final_observed_at: datetime | None
    final_block_number: int | None
    peak_multiple: Decimal | None
    final_multiple: Decimal | None
    peak_pnl_usd: Decimal | None
    final_pnl_usd: Decimal | None
    commit_seq: int
    finalized_at: datetime


@dataclass(frozen=True, slots=True)
class CandidateSignalCommit:
    candidate: InsertResult[Candidate]
    signal: InsertResult[CurrentSignal]


@dataclass(frozen=True, slots=True)
class CanonicalObservationCommit:
    observation: InsertResult[BlockObservation]
    head_sighting: InsertResult[CanonicalHeadSighting]


@dataclass(frozen=True, slots=True)
class SimulatedBuyCommit:
    decision: InsertResult[EntryDecision]
    buy: InsertResult[SimulatedBuy]
    entry: CanonicalObservationCommit
