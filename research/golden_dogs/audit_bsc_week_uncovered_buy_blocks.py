#!/usr/bin/env python3
"""RPC-verify every strict pre-1.02 buy in public-signal-uncovered waves."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.block_signal_timing import classify_block_signal
from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
BUYS = ROOT / "bsc_week_pre_breakout_buys.jsonl"
PUBLIC = ROOT / "bsc_week_public_advance_audit.jsonl"
CROSSINGS = ROOT / "bsc_week_price_crossing_positions.jsonl"
OUTPUT = ROOT / "bsc_week_uncovered_pre_breakout_blocks.jsonl"
LATENCIES = (0, 5, 15, 30, 60, 120)


def main() -> None:
    buys = {_key(row): row for row in _jsonl(BUYS)}
    positions = {
        _key(row): row["rpc_position"] for row in _jsonl(CROSSINGS)
    }
    keys = tuple(
        _key(row) for row in _jsonl(PUBLIC)
        if not any(
            item["event_time_actionable"]
            for item in row["event_time_assessments"]["0"]
        )
    )
    if len(keys) != 11 or len(set(keys)) != 11:
        raise RuntimeError("RPC audit requires exactly 11 public-uncovered waves")
    rows = []
    with PublicBscRpcClient(timeout_seconds=30, attempts=3) as rpc:
        for key in keys:
            wave, motion = buys[key], positions[key]
            verified = []
            for item in wave["buys"]:
                swap = rpc.verify_token_buy(
                    item["transaction_hash"], item["wallet"], wave["address"],
                )
                timing = classify_block_signal(
                    swap.block_number, swap.transaction_index,
                    int(motion["block_number"]), int(motion["transaction_index"]),
                )
                verified.append({
                    "provider_buy": item,
                    "rpc_swap": asdict(swap),
                    "block_timing": asdict(timing),
                })
            rows.append({
                "schema": "debot4.bsc_week_uncovered_pre_breakout_blocks.v1",
                "label": wave["label"], "address": wave["address"],
                "wave_number": wave["wave_number"],
                "first_1_02_transaction": motion,
                "verified_buy_count": len(verified), "buys": verified,
            })
            print(f"{wave['label']} w{wave['wave_number']}: verified={len(verified)}")
    write_jsonl(OUTPUT, rows)
    write_json(
        ROOT / "bsc_week_uncovered_pre_breakout_blocks_summary.json",
        _summary(rows, _jsonl(PUBLIC)),
    )


def _summary(rows, public_rows):
    previous = tuple(
        row for row in rows if any(
            item["block_timing"]["post_confirmation_actionable"]
            for item in row["buys"]
        )
    )
    same_only = tuple(
        row for row in rows if row["buys"] and not any(
            item["block_timing"]["post_confirmation_actionable"]
            for item in row["buys"]
        )
    )
    public_coverage = {
        str(latency): sum(any(
            item["event_time_actionable"]
            for item in row["event_time_assessments"][str(latency)]
        ) for row in public_rows)
        for latency in LATENCIES
    }
    chain_coverage = {
        str(latency): sum(any(
            item["block_timing"]["post_confirmation_actionable"]
            and int(item["rpc_swap"]["block_timestamp"]) + latency
            < int(row["first_1_02_transaction"]["block_timestamp"])
            for item in row["buys"]
        ) for row in rows)
        for latency in LATENCIES
    }
    if len(public_rows) != 32 or any(not row["buys"] for row in rows):
        raise RuntimeError("capture ceiling requires 32 public rows and nonempty buy evidence")
    normal_union = {
        key: public_coverage[key] + chain_coverage[key]
        for key in public_coverage
    }
    same_block = tuple(
        row for row in rows if any(
            item["block_timing"]["mempool_or_builder_only"]
            for item in row["buys"]
        )
    )
    return {
        "schema": "debot4.bsc_week_uncovered_pre_breakout_blocks_summary.v1",
        "wave_count": len(rows),
        "verified_buy_count": sum(row["verified_buy_count"] for row in rows),
        "previous_block_actionable_wave_count": len(previous),
        "previous_block_actionable_waves": tuple(
            f"{row['label']}#{row['wave_number']}" for row in previous
        ),
        "same_block_only_wave_count": len(same_only),
        "same_block_only_waves": tuple(
            f"{row['label']}#{row['wave_number']}" for row in same_only
        ),
        "latency_seconds": LATENCIES,
        "public_event_time_wave_coverage": public_coverage,
        "incremental_normal_confirmation_wave_coverage": chain_coverage,
        "public_or_normal_confirmation_timing_ceiling": normal_union,
        "ideal_mempool_or_builder_order_ceiling_at_zero_latency": (
            public_coverage["0"] + len(previous) + len(same_block)
        ),
        "creator_buy_count": sum(
            item["provider_buy"]["creator_match"] is True
            for row in rows for item in row["buys"]
        ),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BUYS, PUBLIC, CROSSINGS, OUTPUT)
        },
        "warning": (
            "Earlier-block visibility is a timing condition only; it does not prove "
            "wallet skill, predictive precision, or safe execution. Same-block order "
            "is an ideal builder/mempool ceiling, not normal post-confirmation coverage."
        ),
    }


def _key(row):
    return str(row["address"]), int(row["wave_number"])


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
