#!/usr/bin/env python3
"""Snapshot identities and funding hints for incremental pre-breakout wallets."""

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
PUBLIC = ROOT / "bsc_week_public_advance_audit.jsonl"
WALLETS = ROOT / "bsc_week_pre_breakout_wallets.jsonl"
OUTPUT = ROOT / "bsc_week_pre_breakout_wallet_profiles.jsonl"


def main() -> None:
    buys = {_key(row): row for row in _jsonl(BUYS)}
    uncovered = {
        _key(row) for row in _jsonl(PUBLIC)
        if not any(
            item["event_time_actionable"]
            for item in row["event_time_assessments"]["0"]
        )
    }
    repeats = {
        str(row["wallet"]): row for row in _jsonl(WALLETS)
        if row["retrospective_repeat_candidate"] is True
    }
    observations: dict[str, list[dict[str, object]]] = {}
    for key in uncovered:
        for buy in buys[key]["buys"]:
            observations.setdefault(str(buy["wallet"]), []).append({
                "source": "public_uncovered_pre_1_02_buy",
                "label": buys[key]["label"], "address": key[0],
                "wave_number": key[1], "occurred_at": buy["occurred_at"],
                "transaction_hash": buy["transaction_hash"],
                "amount_usd": buy["amount_usd"],
            })
    for wallet, row in repeats.items():
        for item in row["observations"]:
            observations.setdefault(wallet, []).append({
                "source": "retrospective_repeat_winner_buy", **item,
            })
    rows = []
    with PublicGmgnWalletClient(timeout_seconds=30, attempts=3) as client:
        for wallet in sorted(observations):
            try:
                profile = client.fetch_profile("bsc", wallet)
                row = {
                    "schema": "debot4.bsc_week_pre_breakout_wallet_profile.v1",
                    "wallet": wallet, "status": "complete",
                    "profile": asdict(profile),
                    "manipulative_tags": manipulative_wallet_tags(profile.tags),
                    "observations": _deduplicate(observations[wallet]),
                    "as_of_identity_qualified": False,
                    "as_of_skill_qualified": False,
                    "warnings": (
                        "Profile is a current snapshot, not a point-in-time identity proof.",
                        "A public X field does not prove the user controlled the wallet at buy time.",
                    ),
                }
            except Exception as exc:
                row = {
                    "schema": "debot4.bsc_week_pre_breakout_wallet_profile.v1",
                    "wallet": wallet, "status": "error",
                    "error_type": type(exc).__name__,
                    "observations": _deduplicate(observations[wallet]),
                    "as_of_identity_qualified": False,
                    "as_of_skill_qualified": False,
                }
            rows.append(row)
            print(f"{wallet}: {row['status']}")
    write_jsonl(OUTPUT, rows)
    write_json(
        ROOT / "bsc_week_pre_breakout_wallet_profiles_summary.json",
        _summary(rows, uncovered),
    )


def _deduplicate(rows):
    unique = {
        (str(row["source"]), str(row["transaction_hash"])):
        row for row in rows
    }
    return tuple(sorted(unique.values(), key=lambda item: (
        int(item["occurred_at"]), str(item["transaction_hash"]),
        str(item["source"]),
    )))


def _summary(rows, uncovered):
    complete = tuple(row for row in rows if row["status"] == "complete")
    bindings = tuple(
        row for row in complete
        if row["profile"]["x_bound"] is True and row["profile"]["x_handle"]
    )
    funders: dict[str, set[str]] = {}
    for row in complete:
        funder = row["profile"].get("fund_from")
        if funder:
            funders.setdefault(str(funder), set()).add(str(row["wallet"]))
    shared = {
        funder: sorted(wallets) for funder, wallets in funders.items()
        if len(wallets) >= 2
    }
    return {
        "schema": "debot4.bsc_week_pre_breakout_wallet_profiles_summary.v1",
        "public_uncovered_wave_count": len(uncovered),
        "wallet_count": len(rows), "complete_profile_count": len(complete),
        "profile_error_count": len(rows) - len(complete),
        "current_x_bound_profile_count": len(bindings),
        "current_x_bound_profiles": tuple({
            "wallet": row["wallet"], "x_handle": row["profile"]["x_handle"],
            "name": row["profile"]["name"], "tags": row["profile"]["tags"],
        } for row in bindings),
        "manipulative_profile_count": sum(
            bool(row["manipulative_tags"]) for row in complete
        ),
        "shared_funder_groups": shared,
        "as_of_identity_qualified_count": 0,
        "as_of_skill_qualified_count": 0,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (BUYS, PUBLIC, WALLETS, OUTPUT)
        },
        "warnings": (
            "Current profile metadata cannot be backdated to the historical buy.",
            "Winner-selected repetition does not establish wallet precision.",
        ),
    }


def _key(row):
    return str(row["address"]), int(row["wave_number"])


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
