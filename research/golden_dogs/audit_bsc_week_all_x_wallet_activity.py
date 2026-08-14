#!/usr/bin/env python3
"""Audit seven-day activity for every historical X-attributed early wallet."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import time

from debot4.v6.golden_dogs.gmgn_wallet_activity import (
    PublicGmgnWalletActivityClient,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
PROFILES = ROOT / "bsc_week_all_x_wallet_profiles.jsonl"
LEGACY = ROOT / "bsc_week_wallet_x_leads.jsonl"
OUTPUT = ROOT / "bsc_week_all_x_wallet_activity.jsonl"
PERIOD_SECONDS = 7 * 86_400
FREQUENCY_CEILING_PER_DAY = 8.0


def main() -> None:
    candidates = _candidates()
    cached = _valid_cache(_jsonl(OUTPUT) if OUTPUT.exists() else (), candidates)
    legacy = _legacy_activity()
    rows = dict(cached)
    with PublicGmgnWalletActivityClient(timeout_seconds=30, attempts=3) as client:
        for index, candidate in enumerate(candidates, 1):
            wallet = str(candidate["wallet"])
            row = cached.get(wallet) or _legacy_row(candidate, legacy.get(wallet))
            fetched = row is None
            if row is None:
                row = _audit(client, candidate)
            rows[wallet] = row
            write_jsonl(OUTPUT, _ordered(rows.values()))
            print(
                f"{index}/{len(candidates)} {candidate['x_handle']}: "
                f"{row['status']} pages={row.get('page_count', 0)}",
                flush=True,
            )
            if fetched:
                time.sleep(1)
    ordered = _ordered(rows.values())
    write_jsonl(OUTPUT, ordered)
    write_json(ROOT / "bsc_week_all_x_wallet_activity_summary.json", _summary(ordered))


def _audit(client, candidate):
    end = int(candidate["first_observed_buy_at"])
    try:
        result = client.fetch_history(
            str(candidate["wallet"]), end - PERIOD_SECONDS, end, max_pages=200,
        )
        buys = tuple(item for item in result.activities if item.event == "buy")
        return _row(candidate, {
            "coverage_complete": result.coverage_complete,
            "stop_reason": result.stop_reason,
            "page_count": len(result.receipts),
            "activity_count": len(result.activities),
            "buy_transactions": len({item.transaction_hash for item in buys}),
            "unique_tokens_bought": len({item.token_address for item in buys}),
            "receipt_sha256": tuple(item.sha256 for item in result.receipts),
        }, "fresh_provider_fetch")
    except Exception as exc:
        return {
            "schema": "debot4.bsc_week_all_x_wallet_activity.v1",
            "wallet": candidate["wallet"], "x_handle": candidate["x_handle"],
            "signal_at": end, "status": "error",
            "error_type": type(exc).__name__,
            "error_detail": str(exc)[:500],
            "as_of_skill_qualified": False,
        }


def _legacy_row(candidate, activity):
    if activity is None:
        return None
    return _row(candidate, activity, "reused_verified_five_wallet_audit")


def _row(candidate, activity, provenance):
    unique = int(activity["unique_tokens_bought"])
    complete = activity["coverage_complete"] is True
    manipulative = bool(candidate["manipulative_tags"])
    frequency_pass = complete and unique / 7 <= FREQUENCY_CEILING_PER_DAY
    return {
        "schema": "debot4.bsc_week_all_x_wallet_activity.v1",
        "wallet": candidate["wallet"], "x_handle": candidate["x_handle"],
        "signal_at": candidate["first_observed_buy_at"],
        "period_start": int(candidate["first_observed_buy_at"]) - PERIOD_SECONDS,
        "period_end_exclusive": candidate["first_observed_buy_at"],
        "status": "complete" if complete else "incomplete",
        "coverage_complete": complete,
        "stop_reason": activity["stop_reason"],
        "page_count": activity["page_count"],
        "activity_count": activity["activity_count"],
        "buy_transactions": activity["buy_transactions"],
        "unique_tokens_bought": unique,
        "unique_tokens_per_day": unique / 7,
        "frequency_screen_pass": frequency_pass,
        "manipulative_tags": candidate["manipulative_tags"],
        "eligible_for_outcome_denominator_audit": frequency_pass and not manipulative,
        "receipt_sha256": activity["receipt_sha256"],
        "provenance": provenance,
        "as_of_skill_qualified": False,
        "warning": (
            "Frequency is only a preliminary noise screen; every purchased token "
            "still needs a point-in-time pre-peak outcome before skill can qualify."
        ),
    }


def _candidates():
    rows = tuple(row for row in _jsonl(PROFILES) if row["status"] == "complete")
    if len(rows) != 26:
        raise RuntimeError("all-X activity audit requires exactly 26 profiles")
    return tuple(sorted(rows, key=lambda row: str(row["wallet"])))


def _legacy_activity():
    return {
        str(row["wallet"]): row["pre_signal_activity"]
        for row in _jsonl(LEGACY)
    }


def _valid_cache(rows, candidates):
    expected = {
        str(row["wallet"]): int(row["first_observed_buy_at"])
        for row in candidates
    }
    return {
        str(row["wallet"]): row for row in rows
        if row.get("status") in {"complete", "incomplete"}
        and expected.get(str(row["wallet"])) == int(row["signal_at"])
    }


def _ordered(rows):
    return sorted(rows, key=lambda item: str(item["wallet"]))


def _summary(rows):
    complete = tuple(row for row in rows if row["status"] == "complete")
    eligible = tuple(
        row for row in complete if row["eligible_for_outcome_denominator_audit"]
    )
    return {
        "schema": "debot4.bsc_week_all_x_wallet_activity_summary.v1",
        "candidate_count": len(rows), "complete_activity_count": len(complete),
        "activity_error_or_incomplete_count": len(rows) - len(complete),
        "frequency_screen_pass_count": sum(
            row["frequency_screen_pass"] for row in complete
        ),
        "manipulative_wallet_count": sum(
            bool(row["manipulative_tags"]) for row in complete
        ),
        "eligible_for_outcome_denominator_audit_count": len(eligible),
        "eligible_for_outcome_denominator_audit": tuple({
            "wallet": row["wallet"], "x_handle": row["x_handle"],
            "unique_tokens_bought_7d": row["unique_tokens_bought"],
        } for row in eligible),
        "as_of_skill_qualified_count": 0,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (PROFILES, LEGACY, OUTPUT)
        },
        "warning": (
            "This is an as-of activity denominator only; the outcome denominator "
            "and historical identity proof remain incomplete."
        ),
    }


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
