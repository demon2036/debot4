#!/usr/bin/env python3
"""Join independently verified exact-CA X posts to fixed-window markets."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import (
    observation_from_mapping,
    write_json,
    write_jsonl,
)
from debot4.v6.golden_dogs.x_ca_leads import (
    join_verified_x_to_markets,
    verified_leads_from_row,
)


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    args = _args()
    verified_rows = _jsonl(ROOT / args.verified)
    leads = tuple(
        lead for row in verified_rows for lead in verified_leads_from_row(row)
    )
    markets = {}
    for chain in ("bsc", "robinhood"):
        for row in _jsonl(ROOT / f"{chain}_market_candidates.jsonl"):
            observation = observation_from_mapping(row)
            markets[(chain, observation.address)] = observation
    joins = join_verified_x_to_markets(leads, markets)
    write_jsonl(ROOT / args.output, (
        {
            "schema": args.schema,
            "x": asdict(item.lead),
            "market": asdict(item.observation),
            "timing": item.timing,
            "x_is_kol_buy_evidence": False,
        }
        for item in joins
    ))
    unique_leads = {(item.lead.status_url, item.lead.address) for item in joins}
    write_json(ROOT / args.summary, {
        "schema": args.summary_schema,
        "generated_at": datetime.now(UTC),
        "verified_status_rows": len(verified_rows),
        "exact_ca_mentions": len(leads),
        "unique_exact_cas": len({item.address for item in leads}),
        "joined_status_ca_pairs": len(unique_leads),
        "joined_unique_tokens": len({item.lead.address for item in joins}),
        "joined_by_chain": dict(sorted(Counter(
            item.observation.chain for item in joins
        ).items())),
        "timing": dict(sorted(Counter(item.timing for item in joins).items())),
        "warning": (
            "An authored exact-CA post is not proof of KOL status, a buy, causality, "
            "or absence of manipulation"
        ),
    })


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verified", default="grok_chinese_x_verified.jsonl")
    parser.add_argument("--output", default="chinese_x_market_joins.jsonl")
    parser.add_argument("--summary", default="chinese_x_market_join_summary.json")
    parser.add_argument("--schema", default="debot4.chinese_x_market_join.v1")
    parser.add_argument(
        "--summary-schema", default="debot4.chinese_x_market_join_summary.v1",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
