#!/usr/bin/env python3
"""Summarize frozen BSC GMGN/RPC evidence without weakening missing-data gates."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.audit_summary import assess_audit_row
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    rows = [
        json.loads(line) for line in
        (ROOT / "bsc_gmgn_kol_audit_v2.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    records = []
    for row in rows:
        result = assess_audit_row(row)
        clean_buys = [
            item for item in row.get("verified_kol_buys", [])
            if item.get("clean_in_window") is True
        ]
        records.append({
            "schema": "debot4.bsc_gmgn_qualification.v1",
            "address": result.address, "name": row.get("name"),
            "symbol": row.get("symbol"), "outcome": result.outcome,
            "reasons": result.reasons,
            "causal_pre_peak_buy": result.causal_pre_peak_buy,
            "market": row.get("market"),
            "clean_buys": [_compact_buy(item) for item in clean_buys],
        })
    counts = Counter(str(item["outcome"].value) for item in records)
    summary = {
        "schema": "debot4.bsc_gmgn_audit_summary.v1",
        "generated_at": datetime.now(UTC), "candidate_rows": len(rows),
        "history_complete": sum(row.get("gmgn_history_coverage_complete") is True for row in rows),
        "tokens_with_provider_tagged_buy": sum(bool(row.get("gmgn_tagged_buy_count_in_window")) for row in rows),
        "tokens_with_rpc_verified_clean_buy": sum(bool(item["clean_buys"]) for item in records),
        "tokens_with_pre_peak_rpc_verified_clean_buy": sum(item["causal_pre_peak_buy"] for item in records),
        "outcomes": dict(sorted(counts.items())),
        "warning": (
            "PASS requires market>=500K, a clean GMGN KOL buy verified by BSC RPC, "
            "and complete manipulation checks. Missing wash/circular evidence remains WAIT."
        ),
    }
    write_jsonl(ROOT / "bsc_gmgn_qualification.jsonl", records)
    write_json(ROOT / "bsc_gmgn_audit_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, default=str))


def _compact_buy(item: dict) -> dict[str, object]:
    trade = item["provider_trade"]
    profile = item.get("wallet_profile") or {}
    return {
        "wallet": trade.get("wallet"), "transaction_hash": trade.get("transaction_hash"),
        "bought_at": trade.get("timestamp"), "amount_usd": trade.get("amount_usd"),
        "provider_name": trade.get("name"), "provider_x_handle": trade.get("x_handle"),
        "profile_x_handle": profile.get("x_handle"),
        "profile_x_bound": profile.get("x_bound"), "before_market_peak": item.get("before_market_peak"),
    }


if __name__ == "__main__":
    main()
