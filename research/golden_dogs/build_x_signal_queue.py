#!/usr/bin/env python3
"""Build the X-first evidence queue from independently verified intersections."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_account_queue import is_excluded_x_account_role
from debot4.v6.golden_dogs.x_post_semantics import (
    XPostInterpretation,
    XPostSemantic,
    assess_x_post_semantic,
)
from debot4.v6.golden_dogs.x_signal import XSignalEvidence, assess_x_signal


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    accounts = {str(row["stable_user_id"]): row for row in
                _jsonl("x_account_candidate_queue.jsonl")}
    markets = {(row["x"]["status_url"], row["address"]): row for row in
               _jsonl("x_post_market_trajectories.jsonl")}
    reviews = _semantic_reviews()
    rows = []
    for item in _jsonl("x_kol_buy_intersections.jsonl"):
        if item["x_post_timing"] != "pre_peak":
            continue
        identity = str(item["x"]["stable_user_id"])
        account = accounts.get(identity, {})
        audit = item["kol_buy_audit"]
        before = int((audit.get("x_author_wallet_timing") or {}).get(
            "buy_before_post", 0,
        ))
        role = account.get("reviewed_role")
        evidence = XSignalEvidence(
            stable_x_identity=bool(identity), pre_peak_exact_ca_post=True,
            rpc_clean_kol_buy_count=int(audit["rpc_verified_clean_buy_count"]),
            exact_author_wallet_buy_before_post_count=before,
            wallet_x_binding=bool(account.get("wallet_binding_pass")),
            excluded_role=is_excluded_x_account_role(role),
        )
        assessment = assess_x_signal(evidence)
        review = reviews.get((item["x"]["status_url"], item["address"]))
        semantic = XPostSemantic(
            review["semantic"] if review else XPostSemantic.UNREVIEWED,
        )
        semantic_assessment = assess_x_post_semantic(XPostInterpretation(
            semantic=semantic, manually_reviewed=review is not None,
            structural_signal_candidate=assessment.grade.value in {"A", "B"},
            excluded_account_role=evidence.excluded_role,
        ))
        rows.append({
            "schema": "debot4.x_signal_evidence.v2",
            "grade": assessment.grade, "grade_reasons": assessment.reasons,
            "structural_candidate": assessment.structural_candidate,
            "post_semantic": semantic, "post_semantic_review": review,
            "causal_research_candidate": (
                semantic_assessment.causal_research_candidate
            ),
            "semantic_reasons": semantic_assessment.reasons,
            "account_role": role, "address": item["address"],
            "token": item["token"], "x": item["x"],
            "evidence": asdict(evidence), "kol_buy_audit": audit,
            "market_trajectory": markets.get(
                (item["x"]["status_url"], item["address"]),
            ),
            "warning": (
                "Grade is evidence strength, not a win rate, causation verdict, "
                "manipulation PASS, or instruction to trade."
            ),
        })
    rows.sort(key=lambda row: (
        row["grade"].value, row["x"]["published_at"], row["address"],
    ))
    write_jsonl(ROOT / "x_signal_evidence_queue.jsonl", rows)
    write_json(ROOT / "x_signal_evidence_summary.json", _summary(rows))


def _summary(rows: list[dict]) -> dict[str, object]:
    return {
        "schema": "debot4.x_signal_evidence_summary.v2",
        "generated_at": datetime.now(UTC), "pairs": len(rows),
        "accounts": len({row["x"]["stable_user_id"] for row in rows}),
        "tokens": len({row["address"] for row in rows}),
        "grades": dict(sorted(Counter(row["grade"].value for row in rows).items())),
        "semantics": dict(sorted(Counter(
            row["post_semantic"].value for row in rows
        ).items())),
        "manually_reviewed_posts": sum(
            row["post_semantic_review"] is not None for row in rows
        ),
        "causal_research_candidates": sum(
            row["causal_research_candidate"] for row in rows
        ),
        "warning": "Evidence grades do not qualify a golden dog or smart wallet.",
    }


def _semantic_reviews() -> dict[tuple[str, str], dict]:
    rows = _json("x_post_semantic_reviews.json")
    output = {}
    for row in rows:
        key = (row["status_url"], row["address"].lower())
        if key in output:
            raise ValueError(f"duplicate X post semantic review: {key}")
        XPostSemantic(row["semantic"])
        output[key] = row
    return output


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


def _json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
