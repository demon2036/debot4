#!/usr/bin/env python3
"""Validate all weekly exact-CA X reviews and emit a receipt-bound ledger."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_review_ledger import validate_and_join_x_reviews


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bsc_week_x_exact_evidence.jsonl"
REVIEWS = ROOT / "bsc_week_x_exact_semantic_reviews.jsonl"
OUTPUT = ROOT / "bsc_week_x_exact_semantic_evidence.jsonl"
SUMMARY = ROOT / "bsc_week_x_exact_semantic_evidence_summary.json"


def main() -> None:
    joined = validate_and_join_x_reviews(_jsonl(SOURCE), _jsonl(REVIEWS))
    rows = tuple(_row(item) for item in joined)
    if len(rows) != 98 or len({row["tweet_id"] for row in rows}) != 90:
        raise RuntimeError("weekly X ledger must cover 98 associations / 90 posts")
    write_jsonl(OUTPUT, rows)
    write_json(SUMMARY, {
        "schema": "debot4.bsc_week_x_exact_semantic_summary.v1",
        "association_count": len(rows),
        "unique_post_count": len({row["tweet_id"] for row in rows}),
        "target_count": len({row["address"] for row in rows}),
        "semantic_counts": dict(sorted(Counter(
            row["semantic"] for row in rows
        ).items())),
        "origin_counts": dict(sorted(Counter(
            row["origin"] for row in rows
        ).items())),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (SOURCE, REVIEWS, OUTPUT)
        },
        "warning": (
            "Semantic review establishes post meaning only. It does not prove "
            "publisher quality, causal impact, or live first-seen latency."
        ),
    })


def _row(item):
    row = asdict(item)
    row["semantic"] = item.semantic.value
    row["origin"] = item.origin.value
    receipt = {key: row[key] for key in (
        "tweet_id", "address", "semantic", "origin", "reason",
    )}
    row.update({
        "schema": "debot4.bsc_week_x_exact_semantic_evidence.v1",
        "review_sha256": hashlib.sha256(json.dumps(
            receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        ).encode()).hexdigest(),
    })
    return row


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
