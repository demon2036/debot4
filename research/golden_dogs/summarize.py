#!/usr/bin/env python3
"""Build current deterministic aggregates from frozen research rows."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    coverage = _json("coverage.json")
    bsc_audit = _json("bsc_gmgn_audit_summary.json")
    intersections = _json("x_kol_buy_intersection_summary.json")
    accounts = _json("x_account_candidate_summary.json")
    tintin = _json("tintin_directory_profile_summary.json")
    tintin_join = _json("tintin_x_market_join_summary.json")
    signal_patterns = _json("x_signal_pattern_summary.json")
    chains = {row["chain"]: row for row in coverage["chains"]}
    write_json(ROOT / "summary.json", {
        "schema": "debot4.golden_dog_summary.v2",
        "generated_at": datetime.now(UTC),
        "definition": {
            "market": "fixed UTC <=7d window peak MC/FDV >= $500K",
            "kol_buy": "DeBot or GMGN real buy; BSC swap independently RPC-verified",
            "manipulation": "shared funding, concentration and wash/circular checks",
            "causal_timing": "separate label; post-peak buy does not erase buy eligibility",
        },
        "scope": "DeBot launch-source snapshot; not an all-pool chain census",
        "bsc": _coverage(chains["bsc"]) | {
            "kol_buy_audit": bsc_audit,
        },
        "robinhood": _coverage(chains["robinhood"]) | {
            "provider_and_chain_buy_closure_complete": False,
        },
        "x_evidence": {
            "account_queue": accounts,
            "kol_buy_intersections": intersections,
            "reviewed_signal_patterns": signal_patterns,
            "tintin_directory": tintin,
            "tintin_directory_market_join": tintin_join,
        },
        "smart_wallet": {
            "leaderboard_complete": False,
            "rule": "full denominator + selectivity; reject indiscriminate high-frequency",
        },
    })


def _coverage(row: dict) -> dict[str, object]:
    return {
        key: row[key] for key in (
            "window_start", "window_end_exclusive", "universe_tokens",
            "market_observations", "market_statuses", "market_candidates",
            "source_scope_complete", "sources_queried",
        )
    }


def _json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
