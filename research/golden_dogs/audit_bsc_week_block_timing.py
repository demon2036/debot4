#!/usr/bin/env python3
"""Verify strict provider candidates against mined BSC block positions."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.block_signal_timing import classify_block_signal
from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bsc_week_trade_price_evidence.jsonl"
OUTPUT = ROOT / "bsc_week_block_signal_evidence.jsonl"


def main() -> None:
    rows = _jsonl(SOURCE)
    evidence: list[dict[str, object]] = []
    with PublicBscRpcClient(timeout_seconds=30, attempts=3) as rpc:
        for row in rows:
            crossing = row.get("transaction_motion_crossing")
            candidates = [
                item for item in row["provider_candidates"]
                if item["timing"]["strict_advance"] is True
            ]
            if not candidates or crossing is None:
                continue
            motion = rpc.fetch_transaction_position(crossing["transaction_hash"])
            verified = []
            for candidate in candidates:
                signal = rpc.verify_token_buy(
                    candidate["transaction_hash"], candidate["wallet"], row["address"],
                )
                timing = classify_block_signal(
                    signal.block_number, signal.transaction_index,
                    motion.block_number, motion.transaction_index,
                )
                verified.append({
                    "wallet": candidate["wallet"],
                    "x_handle": candidate["x_handle"],
                    "amount_usd": candidate["amount_usd"],
                    "seconds_to_motion": candidate["timing"]["seconds_to_motion"],
                    "signal_swap": asdict(signal),
                    "block_timing": asdict(timing),
                })
            evidence.append({
                "schema": "debot4.bsc_week_block_signal_evidence.v1",
                "label": row["label"], "address": row["address"],
                "wave_number": row["wave_number"],
                "motion_transaction": asdict(motion),
                "candidate_count": len(verified), "candidates": verified,
            })
            print(f"{row['label']} w{row['wave_number']}: verified={len(verified)}")
    write_jsonl(OUTPUT, evidence)
    write_json(ROOT / "bsc_week_block_signal_evidence_summary.json", {
        "schema": "debot4.bsc_week_block_signal_evidence_summary.v1",
        "candidate_wave_count": len(evidence),
        "candidate_count": sum(row["candidate_count"] for row in evidence),
        "post_confirmation_actionable_wave_upper_bound": sum(
            any(item["block_timing"]["post_confirmation_actionable"]
                for item in row["candidates"])
            for row in evidence
        ),
        "same_block_only_wave_count": sum(
            not any(item["block_timing"]["post_confirmation_actionable"]
                    for item in row["candidates"])
            for row in evidence
        ),
        "source_sha256": {
            SOURCE.name: hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            OUTPUT.name: hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        },
        "warning": (
            "Post-confirmation actionability is only a timing gate. Provider labels "
            "still require identity, historical outcomes, and manipulation checks."
        ),
    })


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


if __name__ == "__main__":
    main()
