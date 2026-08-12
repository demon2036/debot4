#!/usr/bin/env python3
"""Retry and merge only failed fixed-window DeBot market observations."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.market_audit import audit_markets
from debot4.v6.golden_dogs.research_scope import windows_for_chain
from debot4.v6.golden_dogs.serialization import (
    observation_from_mapping, write_json, write_jsonl,
)

from collect import _load_universe, client_factory


ROOT = Path(__file__).resolve().parent


def main() -> None:
    args = _args()
    errors = _rows(ROOT / f"{args.chain}_market_errors.jsonl")
    failed = {str(item["address"]).casefold() for item in errors}
    universe = _load_universe(ROOT / f"{args.chain}_universe.jsonl")
    selected = tuple(item for item in universe.tokens if item.address in failed)
    if len(selected) != len(failed):
        raise SystemExit("market error address is missing from frozen universe")
    result = audit_markets(
        client_factory, selected, {args.chain: windows_for_chain(args.chain)},
        workers=args.workers, item_attempts=args.attempts,
    )
    previous = tuple(
        observation_from_mapping(item)
        for item in _rows(ROOT / f"{args.chain}_observations.jsonl")
        if str(item["address"]).casefold() not in failed
    )
    observations = tuple(sorted(
        (*previous, *result.observations), key=lambda item: (item.created_at, item.address),
    ))
    candidates = tuple(item for item in observations if item.meets_peak_threshold)
    write_jsonl(ROOT / f"{args.chain}_observations.jsonl", observations)
    write_jsonl(ROOT / f"{args.chain}_market_candidates.jsonl", candidates)
    write_jsonl(
        ROOT / f"{args.chain}_market_errors.jsonl",
        ({"chain": chain, "address": address, "error_type": error}
         for chain, address, error in result.errors),
    )
    _update_coverage(args.chain, observations, candidates, len(result.errors))
    statuses = Counter(item.status for item in observations)
    print(
        f"{args.chain}: retried={len(selected)} recovered={len(result.observations)} "
        f"errors={len(result.errors)} observed={len(observations)} "
        f"candidates={len(candidates)} statuses={dict(statuses)}",
        flush=True,
    )


def _rows(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())


def _update_coverage(chain: str, observations: tuple, candidates: tuple,
                     error_count: int) -> None:
    path = ROOT / "coverage.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    summaries = payload.get("chains")
    if not isinstance(summaries, list):
        raise ValueError("coverage artifact has invalid schema")
    summary = next((item for item in summaries if item.get("chain") == chain), None)
    if not isinstance(summary, dict):
        raise ValueError("coverage artifact is missing the retried chain")
    summary.update({
        "market_observations": len(observations),
        "market_error_count": error_count,
        "market_candidates": len(candidates),
        "market_statuses": dict(sorted(Counter(item.status for item in observations).items())),
        "multiple_tiers": dict(sorted(Counter(
            tier for item in observations for tier in item.tiers
        ).items())),
    })
    payload["collected_at"] = datetime.now(timezone.utc)
    write_json(path, payload)


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain", choices=("bsc", "robinhood"), required=True)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--attempts", type=int, default=3)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 1 <= args.attempts <= 5:
        parser.error("invalid retry bounds")
    return args


if __name__ == "__main__":
    main()
