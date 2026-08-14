#!/usr/bin/env python3
"""Seal BSC block positions for every transaction-level 1.02 crossing."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bsc_week_trade_price_evidence.jsonl"
OUTPUT = ROOT / "bsc_week_price_crossing_positions.jsonl"


def main() -> None:
    rows = []
    with PublicBscRpcClient(timeout_seconds=30, attempts=3) as rpc:
        for wave in _jsonl(SOURCE):
            crossing = next(
                item["crossing"] for item in wave["transaction_price_ladder"]
                if item["multiple"] == "1.02"
            )
            if crossing is None:
                raise RuntimeError("all audited waves require a 1.02 crossing")
            position = rpc.fetch_transaction_position(crossing["transaction_hash"])
            rows.append({
                "schema": "debot4.bsc_week_price_crossing_position.v1",
                "label": wave["label"], "address": wave["address"],
                "wave_number": wave["wave_number"], "multiple": "1.02",
                "provider_crossing": crossing,
                "rpc_position": asdict(position),
            })
            print(f"{wave['label']} w{wave['wave_number']}: {position.block_number}")
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 crossing positions, got {len(rows)}")
    write_jsonl(OUTPUT, rows)
    write_json(ROOT / "bsc_week_price_crossing_positions_summary.json", {
        "schema": "debot4.bsc_week_price_crossing_position_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows), "multiple": "1.02",
        "source_sha256": {
            SOURCE.name: hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            OUTPUT.name: hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        },
    })


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
