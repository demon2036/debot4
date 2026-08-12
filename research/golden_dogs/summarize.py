#!/usr/bin/env python3
"""Build deterministic aggregate facts from immutable research rows."""

from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
from statistics import median

from debot4.v6.golden_dogs.serialization import write_json


ROOT = Path(__file__).resolve().parent


def main() -> None:
    bsc = _rows("bsc_golden_candidates.jsonl")
    robinhood = _rows("robinhood_golden_candidates.jsonl")
    gap = _rows("robinhood_exact_ca_observations.jsonl")
    kol = _rows("kol_case_observations.jsonl")
    post_rows = _rows("kol_post_evidence.jsonl")
    rank_diff = json.loads((ROOT / "rank_refresh_differences.json").read_text())
    robinhood_union = {
        item["address"] for item in robinhood
    } | {
        item["address"] for item in gap if item["qualifies_gold"]
    } | {
        item["address"]
        for item in kol
        if item["chain"] == "robinhood" and item["qualifies_gold"] is True
    }
    timing = Counter(
        item["timing"] for item in kol if item["qualifies_gold"] is True
    )
    write_json(ROOT / "summary.json", {
        "schema": "debot4.golden_dog_summary.v1",
        "gold_definition": "first observable 1m open to 5m ATH >=10x and approx peak FDV >=$1M",
        "bsc": _chain_summary(bsc) | {"visible_unique_gold_lower_bound": len(bsc)},
        "robinhood": _chain_summary(robinhood) | {
            "rank_gold": len(robinhood),
            "blockscout_gap_gold": sum(item["qualifies_gold"] for item in gap),
            "visible_unique_gold_lower_bound": len(robinhood_union),
        },
        "kol": {
            "distinct_handles_reviewed": len({item["handle"] for item in kol}) + 1,
            "exact_ca_token_cases": len(kol),
            "gold": sum(item["qualifies_gold"] is True for item in kol),
            "not_gold": sum(item["qualifies_gold"] is False for item in kol),
            "unresolved_exact_case": sum(item["qualifies_gold"] is None for item in kol),
            "additional_claim_without_exact_ca": 1,
            "gold_timing": dict(sorted(timing.items())),
            "verified_post_receipts": len(post_rows),
            "attributable_full_wallets": 1,
        },
        "rank_refresh": [{
            "chain": item["chain"],
            "previous_count": item["previous_count"],
            "refreshed_count": item["refreshed_count"],
            "missing_after_refresh": len(item["missing_after_refresh"]),
            "new_after_refresh": len(item["new_after_refresh"]),
            "rank_receipts": item["rank_receipts"],
            "saturated_slices": len(item["saturated_slices"]),
        } for item in rank_diff],
    })


def _chain_summary(rows: list[dict]) -> dict[str, object]:
    count = len(rows)
    launchpads = Counter(item["launchpad"] for item in rows)
    return {
        "gold_rows": count,
        "initial_fdv_median_usd": _median(rows, "initial_fdv_usd"),
        "first_trade_to_peak_median_hours": median(
            (item["peak_at"] - item["first_trade_at"]) / 3600 for item in rows
        ),
        "max_kols_at_most_4": sum(item["max_kols"] <= 4 for item in rows),
        "max_kols_at_most_4_pct": round(
            100 * sum(item["max_kols"] <= 4 for item in rows) / count, 1
        ),
        "launchpads": dict(sorted(launchpads.items())),
    }


def _median(rows: list[dict], key: str) -> float:
    return float(median(float(item[key]) for item in rows))


def _rows(name: str) -> list[dict]:
    return [
        json.loads(line)
        for line in (ROOT / name).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


if __name__ == "__main__":
    main()
