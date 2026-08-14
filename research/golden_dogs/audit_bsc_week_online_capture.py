#!/usr/bin/env python3
"""Build a 32-wave timing ceiling for prediction versus early detection."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.online_capture import (
    assess_early_motion,
    assess_onchain_candidate,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
TRADES = ROOT / "bsc_week_trade_price_evidence.jsonl"
BLOCKS = ROOT / "bsc_week_block_signal_evidence.jsonl"
OUTPUT = ROOT / "bsc_week_online_capture_audit.jsonl"
LATENCIES = (0, 5, 15, 30, 60, 120)


def main() -> None:
    trades = _jsonl(TRADES)
    blocks = {
        (row["address"], int(row["wave_number"])): row
        for row in _jsonl(BLOCKS)
    }
    rows = [_row(item, blocks.get(
        (item["address"], int(item["wave_number"])),
    )) for item in trades]
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 capture rows, got {len(rows)}")
    write_jsonl(OUTPUT, rows)
    write_json(ROOT / "bsc_week_online_capture_audit_summary.json", {
        "schema": "debot4.bsc_week_online_capture_audit_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "transaction_motion_observed_count": sum(
            row["motion_at"] is not None for row in rows
        ),
        "provider_tagged_timing_upper_bound": {
            str(latency): sum(row["provider_tagged_timing_ceiling"][str(latency)]
                              for row in rows)
            for latency in LATENCIES
        },
        "qualified_provider_signal_count": 0,
        "early_1_02_detection_upper_bound": {
            str(latency): sum(row["early_motion"][str(latency)]["actionable"]
                              for row in rows)
            for latency in LATENCIES
        },
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (TRADES, BLOCKS, OUTPUT)
        },
        "warnings": (
            "Provider-tagged coverage is a timing-only ceiling: every candidate "
            "fails the as-of wallet/KOL qualification gate in this audit.",
            "The 1.02x lane is early motion detection, not advance prediction.",
            "Observed winning waves cannot estimate precision; a full launch/control "
            "universe is required before deployment claims.",
        ),
    })


def _row(row, block):
    ladder = {str(item["multiple"]): item for item in row.get(
        "transaction_price_ladder", (),
    )}
    small = _at(ladder.get("1.02"))
    motion = _at(ladder.get("1.20"))
    prior_candidates = tuple(
        item for item in (block or {}).get("candidates", ())
        if item["block_timing"]["post_confirmation_actionable"] is True
    )
    timing_ceiling = {}
    candidate_assessments = {}
    for latency in LATENCIES:
        assessments = tuple(
            assess_onchain_candidate(
                int(item["signal_swap"]["block_timestamp"]),
                int(item["signal_swap"]["block_timestamp"]),
                int((block or {})["motion_transaction"]["block_timestamp"]),
                prior_block=True,
                observation_latency_seconds=latency,
                as_of_qualified=False,
            )
            for item in prior_candidates
        ) if motion is not None else ()
        candidate_assessments[str(latency)] = tuple(asdict(item) for item in assessments)
        timing_ceiling[str(latency)] = any(
            item["signal_swap"]["block_timestamp"] + latency
            < (block or {})["motion_transaction"]["block_timestamp"]
            for item in prior_candidates
        ) if motion is not None else False
    return {
        "schema": "debot4.bsc_week_online_capture_audit.v1",
        "label": row["label"], "address": row["address"],
        "wave_number": row["wave_number"],
        "first_1_02_at": small, "motion_at": motion,
        "seconds_from_1_02_to_motion": (
            None if small is None or motion is None else motion - small
        ),
        "early_motion": {
            str(latency): asdict(assess_early_motion(
                small, motion, observation_latency_seconds=latency,
            )) for latency in LATENCIES
        },
        "provider_tagged_prior_block_candidate_count": len(prior_candidates),
        "provider_tagged_timing_ceiling": timing_ceiling,
        "provider_candidate_assessments": candidate_assessments,
        "qualified_provider_signal": False,
        "qualification_reason": "no_as_of_wallet_or_kol_history_pass",
    }


def _at(step):
    return None if not step or not step["crossing"] else int(
        step["crossing"]["occurred_at"],
    )


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
