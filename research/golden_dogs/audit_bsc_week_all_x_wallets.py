#!/usr/bin/env python3
"""Snapshot every historical X-attributed wallet strictly before first 1.02x."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.wallet_risk import manipulative_wallet_tags


ROOT = Path(__file__).resolve().parent
BUYS = ROOT / "bsc_week_pre_breakout_buys.jsonl"
EXACT_X = ROOT / "bsc_week_x_exact_evidence.jsonl"
OUTPUT = ROOT / "bsc_week_all_x_wallet_profiles.jsonl"


def main() -> None:
    candidates = _candidates()
    rows = []
    with PublicGmgnWalletClient(timeout_seconds=30, attempts=3) as client:
        for candidate in candidates:
            rows.append(_profile(client, candidate))
            print(f"{candidate['x_handle']}: {rows[-1]['status']}")
    write_jsonl(OUTPUT, rows)
    write_json(ROOT / "bsc_week_all_x_wallet_profiles_summary.json", _summary(rows))


def _profile(client, candidate):
    try:
        profile = asdict(client.fetch_profile("bsc", candidate["wallet"]))
        historical = str(candidate["x_handle"]).casefold()
        current = str(profile.get("x_handle") or "").casefold()
        return {
            "schema": "debot4.bsc_week_all_x_wallet_profile.v1",
            **candidate, "status": "complete", "profile": profile,
            "historical_current_handle_match": bool(current and historical == current),
            "current_provider_binding": profile["x_bound"] is True,
            "manipulative_tags": manipulative_wallet_tags(profile["tags"]),
            "as_of_identity_qualified": False,
            "as_of_skill_qualified": False,
            "warnings": (
                "Current provider metadata cannot be backdated to the buy.",
                "Winner-selected appearances do not establish precision or skill.",
            ),
        }
    except Exception as exc:
        return {
            "schema": "debot4.bsc_week_all_x_wallet_profile.v1",
            **candidate, "status": "error", "error_type": type(exc).__name__,
            "as_of_identity_qualified": False, "as_of_skill_qualified": False,
        }


def _candidates():
    grouped: dict[str, dict[str, object]] = {}
    for wave in _jsonl(BUYS):
        for buy in wave["buys"]:
            if not buy.get("x_handle"):
                continue
            wallet = str(buy["wallet"])
            item = grouped.setdefault(wallet, {
                "wallet": wallet, "x_handle": buy["x_handle"],
                "first_observed_buy_at": int(buy["occurred_at"]),
                "buy_count": 0, "observations": [],
            })
            if str(item["x_handle"]).casefold() != str(buy["x_handle"]).casefold():
                raise RuntimeError("one wallet has conflicting historical X handles")
            item["first_observed_buy_at"] = min(
                int(item["first_observed_buy_at"]), int(buy["occurred_at"]),
            )
            item["buy_count"] = int(item["buy_count"]) + 1
            item["observations"].append({
                "label": wave["label"], "address": wave["address"],
                "wave_number": wave["wave_number"],
                "occurred_at": buy["occurred_at"],
                "transaction_hash": buy["transaction_hash"],
                "amount_usd": buy["amount_usd"],
            })
    rows = tuple(sorted(grouped.values(), key=lambda item: str(item["wallet"])))
    if len(rows) != 26 or sum(int(row["buy_count"]) for row in rows) != 49:
        raise RuntimeError("all-X wallet audit requires 26 wallets and 49 buys")
    return rows


def _summary(rows):
    complete = tuple(row for row in rows if row["status"] == "complete")
    manipulative = tuple(row for row in complete if row["manipulative_tags"])
    observations = tuple(item for row in rows for item in row["observations"])
    wallet_handles = {str(row["x_handle"]).casefold() for row in rows}
    exact_authors = {
        str(row["author_handle"]).casefold() for row in _jsonl(EXACT_X)
    }
    return {
        "schema": "debot4.bsc_week_all_x_wallet_profiles_summary.v1",
        "candidate_count": len(rows),
        "historical_x_attributed_buy_count": sum(row["buy_count"] for row in rows),
        "historical_x_attributed_target_count": len({
            str(item["address"]) for item in observations
        }),
        "historical_x_attributed_wave_count": len({
            (str(item["address"]), int(item["wave_number"]))
            for item in observations
        }),
        "complete_profile_count": len(complete),
        "profile_error_count": len(rows) - len(complete),
        "current_provider_binding_count": sum(
            row["current_provider_binding"] for row in complete
        ),
        "historical_current_handle_match_count": sum(
            row["historical_current_handle_match"] for row in complete
        ),
        "manipulative_profile_count": len(manipulative),
        "manipulative_profiles": tuple({
            "wallet": row["wallet"], "x_handle": row["x_handle"],
            "tags": row["manipulative_tags"],
        } for row in manipulative),
        "as_of_identity_qualified_count": 0,
        "as_of_skill_qualified_count": 0,
        "exact_ca_evidence_author_intersection_count": len(
            wallet_handles & exact_authors
        ),
        "exact_ca_evidence_author_intersections": tuple(sorted(
            wallet_handles & exact_authors
        )),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BUYS, EXACT_X, OUTPUT)
        },
        "warnings": (
            "Provider X fields are discovery leads; point-in-time identity and a "
            "control-universe outcome denominator are still required for KOL status.",
            "The exact-CA author intersection is bounded by the reviewed 98-association "
            "X evidence set; zero does not prove that no deleted/private post existed.",
        ),
    }


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
