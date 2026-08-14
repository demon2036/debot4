#!/usr/bin/env python3
"""Constrain verified X posts to the stable-ID account task that produced each lead."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_task_scope import (
    expected_authors_by_status_id,
    scope_verified_status,
)


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
WINDOW_START = datetime(2025, 8, 12, tzinfo=UTC)
WINDOW_END_EXCLUSIVE = datetime(2026, 8, 13, tzinfo=UTC)


def main() -> None:
    args = _args()
    lead_lines = (ROOT / args.leads).read_text(encoding="utf-8").splitlines()
    expected = expected_authors_by_status_id(lead_lines)
    source_rows = _jsonl(ROOT / args.verified)
    rows = tuple(_scoped(row, expected, args.schema) for row in source_rows)
    write_jsonl(ROOT / args.output, rows)
    counts = Counter(str(row["task_scope_status"]) for row in rows)
    accepted = tuple(row for row in rows if row["task_scope_status"] == "accepted")
    write_json(ROOT / args.summary, {
        "schema": args.summary_schema,
        "generated_at": datetime.now(UTC),
        "source_verified_rows": len(source_rows),
        "candidate_status_ids_with_task_provenance": len(expected),
        "task_scope_status_counts": dict(sorted(counts.items())),
        "accepted_unique_stable_ids": len({
            str(row["observed_author_id"]) for row in accepted
        }),
        "window_start": WINDOW_START,
        "window_end_exclusive": WINDOW_END_EXCLUSIVE,
        "warning": "accepted proves task-account authorship and time scope, not KOL quality",
    })


def _scoped(
    row: dict[str, object],
    expected: dict[str, frozenset[str]],
    schema: str,
) -> dict[str, object]:
    verdict, allowed = scope_verified_status(
        row,
        expected_authors=expected,
        window_start=WINDOW_START,
        window_end_exclusive=WINDOW_END_EXCLUSIVE,
    )
    output = dict(row)
    output.update({
        "source_schema": row.get("schema"),
        "schema": schema,
        "direct_x_status": row.get("status"),
        "task_scope_status": verdict,
        "expected_task_author_ids": allowed,
    })
    if verdict not in {"accepted", "direct_x_unavailable"}:
        output["status"] = verdict
    return output


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    return tuple(
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--leads", default="grok_chinese_profile_deep_leads.jsonl")
    parser.add_argument("--verified", default="grok_chinese_profile_deep_x_verified.jsonl")
    parser.add_argument("--output", default="grok_chinese_profile_deep_x_scoped.jsonl")
    parser.add_argument("--summary", default="grok_chinese_profile_deep_x_scope_summary.json")
    parser.add_argument("--schema", default="debot4.grok_chinese_profile_deep_x_scoped.v1")
    parser.add_argument(
        "--summary-schema",
        default="debot4.grok_chinese_profile_deep_x_scope_summary.v1",
    )
    return parser.parse_args()


if __name__ == "__main__":
    main()
