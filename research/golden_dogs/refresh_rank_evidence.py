#!/usr/bin/env python3
"""Refresh rank receipts only when they reproduce the audited address universe."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.collection import collect_universe
from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.sources import SOURCES_BY_CHAIN

from collect import WINDOWS


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent


def client_factory() -> PublicDeBotClient:
    return PublicDeBotClient(timeout_seconds=40, attempts=3)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", action="append", choices=tuple(WINDOWS))
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 16:
        raise SystemExit("--workers must be between 1 and 16")
    chains = tuple(dict.fromkeys(args.chain or WINDOWS))
    coverage_path = ROOT / "coverage.json"
    coverage = json.loads(coverage_path.read_text(encoding="utf-8"))
    summaries = {item["chain"]: item for item in coverage["chains"]}
    differences = []
    for chain in chains:
        start_at, end_at = WINDOWS[chain]
        result = collect_universe(
            client_factory,
            chain,
            SOURCES_BY_CHAIN[chain],
            start_at,
            end_at,
            workers=args.workers,
        )
        old_addresses = _addresses(ROOT / f"{chain}_universe.jsonl")
        new_addresses = {item.address for item in result.tokens}
        write_jsonl(ROOT / f"{chain}_rank_receipts.jsonl", result.receipts)
        summary = summaries[chain]
        summary.update({
            "rank_refresh_receipts": len(result.receipts),
            "rank_refresh_slices_unsaturated": result.coverage_complete,
            "rank_snapshot_reproduced": old_addresses == new_addresses,
            "rank_verified_at": datetime.now(UTC),
        })
        if old_addresses != new_addresses:
            differences.append({
                "chain": chain,
                "previous_count": len(old_addresses),
                "refreshed_count": len(new_addresses),
                "missing_after_refresh": sorted(old_addresses - new_addresses),
                "new_after_refresh": sorted(new_addresses - old_addresses),
                "rank_receipts": len(result.receipts),
                "rank_slices_unsaturated": result.coverage_complete,
                "saturated_slices": [asdict(item) for item in result.saturated_slices],
            })
            continue
        summary.update({
            "rank_evidence_reused": False,
            "rank_receipts": len(result.receipts),
            "rank_slices_unsaturated": result.coverage_complete,
            "saturated_slices": [asdict(item) for item in result.saturated_slices],
            "rank_verified_at": datetime.now(UTC),
        })
        print(
            f"{chain}: addresses={len(new_addresses)} receipts={len(result.receipts)} "
            f"saturated={len(result.saturated_slices)}",
            flush=True,
        )
    write_json(ROOT / "rank_refresh_differences.json", differences)
    write_json(coverage_path, coverage)
    if any(item["new_after_refresh"] for item in differences):
        raise SystemExit("rank refresh added historical addresses; market audit must be rerun")


def _addresses(path: Path) -> set[str]:
    return {
        str(json.loads(line)["address"]).casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


if __name__ == "__main__":
    main()
