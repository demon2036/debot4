#!/usr/bin/env python3
"""Build fixed-window BSC and Robinhood launch-source research artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import json

from debot4.v6.golden_dogs.collection import collect_universe
from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.market_audit import audit_markets
from debot4.v6.golden_dogs.research_scope import CHAIN_BOUNDS, windows_for_chain
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.sources import SOURCE_CATALOG_EVIDENCE, SOURCES_BY_CHAIN


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
WINDOWS = CHAIN_BOUNDS


def client_factory() -> PublicDeBotClient:
    return PublicDeBotClient(timeout_seconds=40, attempts=3)


def collect_chain(chain: str, *, workers: int) -> dict[str, object]:
    start_at, end_at = WINDOWS[chain]
    universe = collect_universe(
        client_factory,
        chain,
        SOURCES_BY_CHAIN[chain],
        start_at,
        end_at,
        workers=workers,
    )
    write_jsonl(ROOT / f"{chain}_universe.jsonl", universe.tokens)
    return audit_chain(chain, universe, workers=workers)


def audit_chain(
    chain: str,
    universe,
    *,
    workers: int,
    rank_evidence_reused: bool = False,
) -> dict[str, object]:
    start_at, end_at = WINDOWS[chain]
    audit = audit_markets(
        client_factory,
        universe.tokens,
        {chain: windows_for_chain(chain)},
        workers=workers,
    )
    write_jsonl(ROOT / f"{chain}_observations.jsonl", audit.observations)
    market_candidates = tuple(
        item for item in audit.observations if item.meets_peak_threshold
    )
    write_jsonl(ROOT / f"{chain}_market_candidates.jsonl", market_candidates)
    write_jsonl(
        ROOT / f"{chain}_market_errors.jsonl",
        ({"chain": item[0], "address": item[1], "error_type": item[2]} for item in audit.errors),
    )
    statuses = Counter(item.status for item in audit.observations)
    tiers = Counter(tier for item in audit.observations for tier in item.tiers)
    return {
        "chain": chain,
        "window_start": start_at,
        "window_end_exclusive": end_at,
        "source_catalog_evidence": SOURCE_CATALOG_EVIDENCE,
        "sources_queried": list(SOURCES_BY_CHAIN[chain]),
        "universe_tokens": len(universe.tokens),
        "rank_receipts": None if rank_evidence_reused else len(universe.receipts),
        "rank_slices_unsaturated": (
            None if rank_evidence_reused else universe.coverage_complete
        ),
        "rank_evidence_reused": rank_evidence_reused,
        "source_scope_complete": False,
        "saturated_slices": (
            None
            if rank_evidence_reused
            else [asdict(item) for item in universe.saturated_slices]
        ),
        "market_observations": len(audit.observations),
        "market_error_count": len(audit.errors),
        "market_statuses": dict(sorted(statuses.items())),
        "multiple_tiers": dict(sorted(tiers.items())),
        "market_candidates": len(market_candidates),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--chain",
        action="append",
        choices=tuple(WINDOWS),
        help="collect one chain; default collects both",
    )
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument(
        "--reuse-universe",
        action="store_true",
        help="reuse an existing chain_universe.jsonl after interrupted market audit",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 1 <= args.workers <= 16:
        raise SystemExit("--workers must be between 1 and 16")
    chains = tuple(dict.fromkeys(args.chain or WINDOWS))
    summaries = []
    for chain in chains:
        universe_path = ROOT / f"{chain}_universe.jsonl"
        if args.reuse_universe and universe_path.exists():
            universe = _load_universe(universe_path)
            summary = audit_chain(
                chain,
                universe,
                workers=args.workers,
                rank_evidence_reused=True,
            )
            summaries.append(summary)
        else:
            summaries.append(collect_chain(chain, workers=args.workers))
    coverage_path = ROOT / "coverage.json"
    previous = _load_previous_summaries(coverage_path)
    previous.update({str(item["chain"]): item for item in summaries})
    write_json(
        coverage_path,
        {
            "schema": "debot4.golden_dog_coverage.v1",
            "collected_at": datetime.now(UTC),
            "scope_warning": (
                "DeBot launch-source snapshot only; not all pools, and historical completed "
                "rows can disappear between identical rank queries"
            ),
            "market_candidate_definition": {
                "window": "fixed consecutive UTC windows of at most seven days",
                "min_approx_peak_fdv_usd": "500000",
                "sensitivity_tiers": ["3x", "10x", "30x", "100x"],
                "note": "multiple tiers are measurements, not eligibility gates",
            },
            "chains": [previous[key] for key in sorted(previous)],
        },
    )
    for summary in summaries:
        print(
            f"{summary['chain']}: universe={summary['universe_tokens']} "
            f"observed={summary['market_observations']} "
            f"market_candidates={summary['market_candidates']} "
            f"errors={summary['market_error_count']}",
            flush=True,
        )


def _load_universe(path: Path):
    from debot4.v6.golden_dogs.collection import UniverseResult
    from debot4.v6.golden_dogs.models import TokenSeed

    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    tokens = tuple(
        TokenSeed(
            chain=row["chain"],
            address=row["address"],
            name=row["name"],
            symbol=row["symbol"],
            launchpad=row["launchpad"],
            created_at=row["created_at"],
            creator_address=row["creator_address"],
            rank_supply=(Decimal(row["rank_supply"]) if row["rank_supply"] else None),
            current_kols=row["current_kols"],
            max_kols=row["max_kols"],
            social_urls=tuple(row["social_urls"]),
            discovered_sources=tuple(row["discovered_sources"]),
        )
        for row in rows
    )
    return UniverseResult(tokens, (), ())


def _load_previous_summaries(path: Path) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    chains = payload.get("chains", []) if isinstance(payload, dict) else []
    return {
        str(item["chain"]): item
        for item in chains
        if isinstance(item, dict) and isinstance(item.get("chain"), str)
    }


if __name__ == "__main__":
    main()
