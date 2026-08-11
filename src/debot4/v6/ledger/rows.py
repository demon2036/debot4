"""SQLite row decoders kept separate from ledger behavior."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
import sqlite3

from .codec import from_us
from .models import (
    BlockObservation,
    Candidate,
    CanonicalHeadSighting,
    CurrentSignal,
    EntryDecision,
    HistoricalKolEvidence,
    OneHourResult,
    SimulatedBuy,
)


def candidate(row: sqlite3.Row) -> Candidate:
    return Candidate(
        str(row["candidate_id"]), str(row["chain"]), str(row["token_address"]),
        from_us(int(row["detected_at_us"])), from_us(int(row["available_at_us"])),
        str(row["source"]), str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def signal(row: sqlite3.Row) -> CurrentSignal:
    return CurrentSignal(
        str(row["signal_id"]), str(row["candidate_id"]), str(row["chain"]),
        str(row["token_address"]), from_us(int(row["event_at_us"])),
        from_us(int(row["available_at_us"])), str(row["signal_kind"]),
        str(row["source"]), str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def kol_evidence(row: sqlite3.Row) -> HistoricalKolEvidence:
    return HistoricalKolEvidence(
        str(row["evidence_id"]), str(row["chain"]), str(row["token_address"]),
        str(row["signal_id"]), from_us(int(row["event_at_us"])),
        from_us(int(row["available_at_us"])), from_us(int(row["qualified_at_us"])),
        str(row["source"]), str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def decision(row: sqlite3.Row) -> EntryDecision:
    return EntryDecision(
        str(row["decision_id"]), str(row["candidate_id"]), str(row["signal_id"]),
        None if row["kol_evidence_id"] is None else str(row["kol_evidence_id"]),
        from_us(int(row["decided_at_us"])), str(row["status"]), str(row["reason"]),
        str(row["source"]), str(row["strategy_version"]),
        str(row["metadata_json"]), int(row["commit_seq"]),
        from_us(int(row["inserted_at_us"])),
    )


def buy(row: sqlite3.Row) -> SimulatedBuy:
    return SimulatedBuy(
        str(row["buy_id"]), str(row["decision_id"]), str(row["candidate_id"]),
        str(row["signal_id"]), str(row["chain"]), str(row["token_address"]),
        from_us(int(row["executed_at_us"])), int(row["block_number"]),
        str(row["block_hash"]), Decimal(row["entry_fdv_usd"]),
        Decimal(row["notional_usd"]), Decimal(row["entry_position_value_usd"]),
        str(row["source"]), str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def observation(row: sqlite3.Row) -> BlockObservation:
    return BlockObservation(
        str(row["observation_id"]), str(row["buy_id"]), int(row["block_number"]),
        str(row["block_hash"]), str(row["parent_hash"]),
        from_us(int(row["observed_at_us"])), from_us(int(row["available_at_us"])),
        Decimal(row["fdv_usd"]), Decimal(row["position_value_usd"]),
        str(row["source"]), str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def head_sighting(row: sqlite3.Row) -> CanonicalHeadSighting:
    return CanonicalHeadSighting(
        str(row["sighting_id"]), str(row["buy_id"]), int(row["block_number"]),
        str(row["block_hash"]), from_us(int(row["sighted_at_us"])),
        from_us(int(row["available_at_us"])), str(row["source"]),
        str(row["evidence_uri"]), str(row["metadata_json"]),
        int(row["commit_seq"]), from_us(int(row["inserted_at_us"])),
    )


def outcome(row: sqlite3.Row) -> OneHourResult:
    decimal_or_none = lambda key: None if row[key] is None else Decimal(row[key])
    time_or_none = lambda key: None if row[key] is None else from_us(int(row[key]))
    int_or_none = lambda key: None if row[key] is None else int(row[key])
    return OneHourResult(
        buy_id=str(row["buy_id"]), status=str(row["status"]), reason=row["reason"],
        window_ends_at=from_us(int(row["window_ends_at_us"])),
        cutoff_at=from_us(int(row["cutoff_at_us"])),
        coverage_complete_through=from_us(
            int(row["coverage_complete_through_us"])
        ),
        allowed_lateness=timedelta(microseconds=int(row["allowed_lateness_us"])),
        observation_count=int(row["observation_count"]),
        max_gap=timedelta(microseconds=int(row["max_gap_us"])),
        max_allowed_gap=timedelta(microseconds=int(row["max_allowed_gap_us"])),
        peak_fdv_usd=decimal_or_none("peak_fdv_usd"),
        peak_position_value_usd=decimal_or_none("peak_position_value_usd"),
        peak_observed_at=time_or_none("peak_observed_at_us"),
        peak_block_number=int_or_none("peak_block_number"),
        final_fdv_usd=decimal_or_none("final_fdv_usd"),
        final_position_value_usd=decimal_or_none("final_position_value_usd"),
        final_observed_at=time_or_none("final_observed_at_us"),
        final_block_number=int_or_none("final_block_number"),
        peak_multiple=decimal_or_none("peak_multiple"),
        final_multiple=decimal_or_none("final_multiple"),
        peak_pnl_usd=decimal_or_none("peak_pnl_usd"),
        final_pnl_usd=decimal_or_none("final_pnl_usd"),
        commit_seq=int(row["commit_seq"]),
        finalized_at=from_us(int(row["inserted_at_us"])),
    )
