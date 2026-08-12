#!/usr/bin/env python3
"""Verify provider KOL-rank wallet/X bindings; rank profit never qualifies a signal."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_binding import WalletXIdentity, assess_x_binding
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    args = _args()
    source = json.loads((ROOT / args.input).read_text(encoding="utf-8"))
    rows = source.get("rows", [])
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(_verify, row): row["wallet"] for row in rows}
        verified = [future.result() for future in as_completed(pending)]
    verified.sort(key=lambda row: (str(row["rank_x_handle"]).casefold(), row["wallet"]))
    write_jsonl(ROOT / args.output, verified)
    write_json(ROOT / args.summary, _summary(verified, source))
    print(json.dumps(_summary(verified, source), ensure_ascii=False, default=str))


def _verify(row: dict) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "debot4.gmgn_kol_rank_x_verification.v1",
        "wallet": row["wallet"], "rank_name": row.get("name"),
        "rank_x_handle": row.get("x_handle"), "rank_tags": row.get("tags"),
        "transactions_7d": row.get("transactions_7d"), "buys_7d": row.get("buys_7d"),
        "rank_is_qualification": False, "verified_at": datetime.now(UTC),
    }
    try:
        with PublicGmgnWalletClient() as client:
            profile = client.fetch_profile("bsc", str(row["wallet"]))
        x_observation = XProfileClient().fetch_observation(str(row["x_handle"]))
        assessment = assess_x_binding(WalletXIdentity(
            wallet=str(row["wallet"]), provider_activity_handle=str(row["x_handle"]),
            public_profile_handle=profile.public_x_handle,
            stat_profile_handle=profile.stat_x_handle, provider_bound=profile.x_bound,
            fxtwitter_handle=x_observation.profile.handle,
            fxtwitter_user_id=x_observation.profile.user_id,
        ))
        base.update({
            "status": "complete", "gmgn_profile": asdict(profile),
            "x_profile": asdict(x_observation), "x_binding": asdict(assessment),
            "frequency_screen": _frequency(row),
        })
    except Exception as exc:
        base.update({"status": "error", "error_type": type(exc).__name__})
    return base


def _frequency(row: dict) -> dict[str, object]:
    transactions = int(row.get("transactions_7d") or 0)
    buys = int(row.get("buys_7d") or 0)
    high = transactions > 350 or buys > 56
    return {
        "verdict": "REJECT" if high else "WAIT",
        "reason": "provider_rank_high_frequency" if high else "full_history_required",
    }


def _summary(rows: list[dict], source: dict) -> dict[str, object]:
    return {
        "schema": "debot4.gmgn_kol_rank_x_summary.v1",
        "generated_at": datetime.now(UTC), "provider_rows": source.get("provider_rows"),
        "x_attributed_rows": len(rows),
        "complete": sum(item["status"] == "complete" for item in rows),
        "binding_pass": sum(
            item.get("x_binding", {}).get("verdict") == "PASS" for item in rows
        ),
        "high_frequency_reject": sum(
            item.get("frequency_screen", {}).get("verdict") == "REJECT" for item in rows
        ),
        "warning": "Wallet rank is an X/account lead pool, not a smart-wallet leaderboard.",
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="gmgn_bsc_kol_rank_7d.json")
    parser.add_argument("--output", default="gmgn_bsc_kol_rank_x_verified.jsonl")
    parser.add_argument("--summary", default="gmgn_bsc_kol_rank_x_summary.json")
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 10:
        parser.error("workers must be between one and ten")
    return args


if __name__ == "__main__":
    main()
