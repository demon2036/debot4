#!/usr/bin/env python3
"""Build an independently verified X-account queue from real GMGN/RPC buys."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_binding import WalletXIdentity, assess_x_binding
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    args = _args()
    wallets = _wallets(ROOT / args.input)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(_verify, row): row["wallet"] for row in wallets.values()}
        rows = [future.result() for future in as_completed(pending)]
    rows.sort(key=lambda row: (-int(row["eligible_token_count"]), str(row["wallet"])))
    write_jsonl(ROOT / args.output, rows)
    write_json(ROOT / args.summary, _summary(rows))
    print(json.dumps(_summary(rows), ensure_ascii=False, default=str))


def _wallets(path: Path) -> dict[str, dict]:
    output: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for buy in row.get("verified_kol_buys", []):
            if buy.get("clean_in_window") is not True:
                continue
            trade, profile = buy["provider_trade"], buy.get("wallet_profile") or {}
            wallet = str(trade["wallet"])
            item = output.setdefault(wallet, {
                "wallet": wallet, "provider_profile": profile,
                "activity_handles": set(), "tokens": set(), "causal_tokens": set(),
                "buy_transactions": set(), "evidence_transactions": [],
            })
            if trade.get("x_handle"):
                item["activity_handles"].add(str(trade["x_handle"]).lstrip("@"))
            item["tokens"].add(str(row["address"]))
            if buy.get("causal_pre_peak") is True:
                item["causal_tokens"].add(str(row["address"]))
            tx = str(trade["transaction_hash"])
            item["buy_transactions"].add(tx)
            if len(item["evidence_transactions"]) < 5:
                item["evidence_transactions"].append({
                    "token": row["address"], "transaction_hash": tx,
                    "bought_at": trade["timestamp"],
                    "before_market_peak": buy.get("before_market_peak"),
                })
    return output


def _verify(row: dict) -> dict[str, object]:
    profile = row["provider_profile"]
    handles = {str(item).casefold(): str(item) for item in row["activity_handles"]}
    current = str(profile.get("x_handle") or "")
    activity = handles.get(current.casefold(), current or None)
    base: dict[str, object] = {
        "schema": "debot4.bsc_audit_wallet_x.v1", "wallet": row["wallet"],
        "provider_name": profile.get("name"), "provider_tags": profile.get("tags"),
        "provider_x_handle": current or None, "provider_x_bound": profile.get("x_bound"),
        "activity_handles": sorted(row["activity_handles"], key=str.casefold),
        "eligible_token_count": len(row["tokens"]),
        "pre_peak_token_count": len(row["causal_tokens"]),
        "buy_transaction_count": len(row["buy_transactions"]),
        "sample_rpc_verified_buys": row["evidence_transactions"],
        "smart_wallet_qualified": False,
        "smart_wallet_reason": "full_activity_denominator_and_outcomes_required",
        "verified_at": datetime.now(UTC),
    }
    if not current:
        base.update({"status": "no_x_handle"})
        return base
    try:
        x_observation = XProfileClient().fetch_observation(current)
        binding = assess_x_binding(WalletXIdentity(
            wallet=row["wallet"], provider_activity_handle=activity,
            public_profile_handle=profile.get("public_x_handle"),
            stat_profile_handle=profile.get("stat_x_handle"),
            provider_bound=profile.get("x_bound"),
            fxtwitter_handle=x_observation.profile.handle,
            fxtwitter_user_id=x_observation.profile.user_id,
        ))
        base.update({
            "status": "complete", "x_profile": {
                "handle": x_observation.profile.handle,
                "stable_user_id": x_observation.profile.user_id,
                "display_name": x_observation.profile.display_name,
                "description": x_observation.profile.description,
                "source_url": x_observation.source_url,
                "payload_sha256": x_observation.sha256,
                "fetched_at": x_observation.profile.fetched_at,
            }, "x_binding": {
                "verdict": binding.verdict, "canonical_handle": binding.canonical_handle,
                "stable_user_id": binding.stable_user_id, "reasons": binding.reasons,
            },
        })
    except Exception as exc:
        base.update({"status": "error", "error_type": type(exc).__name__})
    return base


def _summary(rows: list[dict]) -> dict[str, object]:
    return {
        "schema": "debot4.bsc_audit_wallet_x_summary.v1",
        "generated_at": datetime.now(UTC), "wallets": len(rows),
        "complete_x_profiles": sum(item["status"] == "complete" for item in rows),
        "binding_pass": sum(item.get("x_binding", {}).get("verdict") == "PASS" for item in rows),
        "multi_token_wallets": sum(int(item["eligible_token_count"]) >= 2 for item in rows),
        "pre_peak_multi_token_wallets": sum(int(item["pre_peak_token_count"]) >= 2 for item in rows),
        "warning": (
            "This is an X/KOL investigation queue from verified buys. It is not a "
            "smart-wallet ranking; complete activity denominators are absent."
        ),
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="bsc_gmgn_kol_audit_v2.jsonl")
    parser.add_argument("--output", default="bsc_audit_wallet_x_verified.jsonl")
    parser.add_argument("--summary", default="bsc_audit_wallet_x_summary.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("workers must be between one and twelve")
    return args


if __name__ == "__main__":
    main()
