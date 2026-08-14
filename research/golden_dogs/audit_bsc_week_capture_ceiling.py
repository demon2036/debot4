#!/usr/bin/env python3
"""Merge strict pre-1.02 public, provider and early-motion capture lanes."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.block_signal_timing import classify_block_signal
from debot4.v6.golden_dogs.online_capture import (
    assess_early_motion, assess_onchain_candidate, combine_capture_lanes,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.trade_price_timing import (
    TransactionPriceCrossing, strictly_precedes_crossing,
)


ROOT = Path(__file__).resolve().parent
TRADES = ROOT / "bsc_week_trade_price_evidence.jsonl"
BLOCKS = ROOT / "bsc_week_block_signal_evidence.jsonl"
PUBLIC = ROOT / "bsc_week_public_advance_audit.jsonl"
CROSSINGS = ROOT / "bsc_week_price_crossing_positions.jsonl"
OUTPUT = ROOT / "bsc_week_capture_ceiling_audit.jsonl"
LATENCIES = (0, 5, 15, 30, 60, 120)


def main() -> None:
    public = {_key(row): row for row in _jsonl(PUBLIC)}
    blocks = {_key(row): row for row in _jsonl(BLOCKS)}
    crossings = {_key(row): row["rpc_position"] for row in _jsonl(CROSSINGS)}
    rows = [
        _wave(row, public[_key(row)], blocks.get(_key(row)), crossings[_key(row)])
        for row in _jsonl(TRADES)
    ]
    if len(rows) != 32 or len({_key(row) for row in rows}) != 32:
        raise RuntimeError("capture ceiling must cover exactly 32 unique waves")
    write_jsonl(OUTPUT, rows)
    write_json(
        ROOT / "bsc_week_capture_ceiling_audit_summary.json",
        _summary(rows),
    )


def _wave(trade, public, block, crossing_position):
    first_small = {
        **_crossing(trade, "1.02"),
        "block_number": crossing_position["block_number"],
        "transaction_index": crossing_position["transaction_index"],
        "block_timestamp": crossing_position["block_timestamp"],
        "rpc_receipt": crossing_position["receipt"],
    }
    motion = _crossing(trade, "1.20")
    candidates = _pre_small_candidates(trade, block, first_small)
    latency_rows = {}
    for latency in LATENCIES:
        public_rows = public["event_time_assessments"].get(str(latency), ())
        provider = tuple(_provider(item, first_small, latency) for item in candidates)
        early = assess_early_motion(
            _at(first_small), _at(motion), observation_latency_seconds=latency,
        )
        combined = combine_capture_lanes(
            (
                (item["event_time_actionable"],
                 item.get("freshness") == "fresh_pre_motion")
                for item in public_rows
            ),
            provider,
            early,
        )
        latency_rows[str(latency)] = {
            "coverage": asdict(combined),
            "provider_assessments": tuple(asdict(item) for item in provider),
            "early_motion_assessment": asdict(early),
        }
    return {
        "schema": "debot4.bsc_week_capture_ceiling_audit.v1",
        "label": trade["label"], "address": trade["address"],
        "wave_number": trade["wave_number"],
        "first_1_02_crossing": first_small,
        "first_1_20_crossing": motion,
        "pre_1_02_provider_candidate_count": len(candidates),
        "pre_1_02_provider_candidates": candidates,
        "latency_assessments": latency_rows,
        "warnings": (
            "Public coverage is a published-at subscription counterfactual, not observed first-seen.",
            "Provider candidates are timing-only because none passed an as-of skill gate.",
            "Early motion starts at 1.02x and is detection, never advance prediction.",
        ),
    }


def _pre_small_candidates(trade, block, crossing):
    if crossing is None or block is None:
        return ()
    by_tx = {
        item["signal_swap"]["transaction_hash"]: item
        for item in block.get("candidates", ())
    }
    crossing_order = TransactionPriceCrossing(
        threshold_price_usd=Decimal(str(crossing["threshold_price_usd"])),
        occurred_at=int(crossing["occurred_at"]),
        provider_sequence=crossing.get("provider_sequence"),
        transaction_hash=crossing["transaction_hash"],
        same_second_trade_count=int(crossing["same_second_trade_count"]),
        order_complete=bool(crossing["order_complete"]),
    )
    result = []
    for item in trade.get("provider_candidates", ()):
        if not strictly_precedes_crossing(
            int(item["occurred_at"]), item.get("provider_sequence"), crossing_order,
        ):
            continue
        verified = by_tx.get(item["transaction_hash"])
        if verified is None:
            raise RuntimeError("strict pre-1.02 provider buy lacks RPC evidence")
        result.append({
            "wallet": item["wallet"], "x_handle": item.get("x_handle"),
            "provider_class": item["provider_class"],
            "provider_matched_tags": item["provider_matched_tags"],
            "amount_usd": item["amount_usd"],
            "provider_sequence": item["provider_sequence"],
            "signal_swap": verified["signal_swap"],
            "block_timing": verified["block_timing"],
            "as_of_qualified": False,
        })
    return tuple(result)


def _provider(item, crossing, latency):
    timing = classify_block_signal(
        int(item["signal_swap"]["block_number"]),
        int(item["signal_swap"]["transaction_index"]),
        int(crossing["block_number"]), int(crossing["transaction_index"]),
    )
    return assess_onchain_candidate(
        int(item["signal_swap"]["block_timestamp"]),
        int(item["signal_swap"]["block_timestamp"]),
        int(crossing["block_timestamp"]),
        prior_block=timing.post_confirmation_actionable,
        observation_latency_seconds=latency,
        as_of_qualified=item["as_of_qualified"],
    )


def _crossing(row, multiple):
    raw = next((item["crossing"] for item in row["transaction_price_ladder"]
                if item["multiple"] == multiple), None)
    return raw


def _summary(rows):
    coverage = {
        str(latency): {
            name: sum(row["latency_assessments"][str(latency)]["coverage"][name]
                      for row in rows)
            for name in next(iter(rows))["latency_assessments"][str(latency)]["coverage"]
        }
        for latency in LATENCIES
    }
    zero = coverage["0"]
    uncovered = [
        f"{row['label']}#{row['wave_number']}" for row in rows
        if not row["latency_assessments"]["0"]["coverage"]["timing_union_ceiling"]
    ]
    return {
        "schema": "debot4.bsc_week_capture_ceiling_audit_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows), "latency_coverage": coverage,
        "pre_1_02_provider_candidate_wave_count": sum(
            row["pre_1_02_provider_candidate_count"] > 0 for row in rows
        ),
        "pre_1_02_provider_candidate_count": sum(
            row["pre_1_02_provider_candidate_count"] for row in rows
        ),
        "zero_latency_timing_union_uncovered": uncovered,
        "zero_latency_timing_union_uncovered_count": len(uncovered),
        "claims": {
            "public_event_time_advance_ceiling": zero["public_advance"],
            "fresh_public_event_time_advance_ceiling": zero["fresh_public_advance"],
            "public_or_unqualified_provider_timing_ceiling": zero["timing_union_ceiling"],
            "qualified_provider_advance": zero["qualified_provider_advance"],
        },
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (TRADES, BLOCKS, PUBLIC, CROSSINGS)
        },
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "warnings": (
            "Winning-wave recall is not precision and cannot prove profitability.",
            "The timing union includes unqualified provider labels and is not deployable coverage.",
            "Guaranteed recall is impossible for private, deleted, same-block, or unsupported signals.",
        ),
    }


def _at(crossing):
    return None if crossing is None else int(crossing["occurred_at"])


def _key(row):
    return str(row["address"]), int(row["wave_number"])


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
