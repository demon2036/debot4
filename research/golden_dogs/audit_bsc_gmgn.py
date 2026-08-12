#!/usr/bin/env python3
"""Restart-safe BSC market/KOL/RPC/manipulation evidence audit."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
from pathlib import Path

from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient
from debot4.v6.golden_dogs.gmgn_public import PublicGmgnClient
from debot4.v6.golden_dogs.gmgn_trade_history import fetch_kol_trades_in_window
from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient
from debot4.v6.golden_dogs.manipulation import assess_manipulation
from debot4.v6.golden_dogs.serialization import json_value


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent


def main() -> None:
    args = _args()
    candidates = _candidates(ROOT / args.observations)
    selected = candidates[args.offset:args.offset + args.limit]
    output = ROOT / args.output
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        completed = _completed(journal)
        selected = tuple(row for row in selected if row["address"] not in completed)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            jobs = {pool.submit(_audit, row): row["address"] for row in selected}
            for future in as_completed(jobs):
                try:
                    row = future.result()
                except Exception as exc:
                    row = {
                        "schema": "debot4.bsc_gmgn_kol_audit.v2",
                        "address": jobs[future], "status": "error",
                        "error_type": type(exc).__name__,
                    }
                _append(journal, row)
                print(f"{row['address']} {row['status']}", flush=True)


def _audit(candidate: dict[str, object]) -> dict[str, object]:
    token = str(candidate["address"])
    start, end = int(candidate["window_start"]), int(candidate["window_end_exclusive"])
    with PublicGmgnClient() as gmgn:
        history = fetch_kol_trades_in_window(gmgn, token, start, end)
        risk = gmgn.fetch_risk("bsc", token)
    buys = tuple(item for item in history.trades if item.event == "buy")
    verified = _verify_swaps(buys, candidate)
    verified_wallets = tuple(sorted({
        str(item["provider_trade"]["wallet"])
        for item in verified if item.get("chain_verified")
    }))
    profiles, profile_errors = _profiles(verified_wallets)
    profile_by_wallet = {profile.wallet: profile for profile in profiles}
    for item in verified:
        wallet = str(item["provider_trade"]["wallet"])
        profile = profile_by_wallet.get(wallet)
        item["wallet_profile"] = asdict(profile) if profile else None
        item["clean_in_window"] = bool(
            item.get("chain_verified")
            and profile is not None and "wash_trader" not in profile.tags
        )
        item["causal_pre_peak"] = bool(
            item["clean_in_window"] and item.get("before_market_peak")
        )
    manipulation = assess_manipulation(
        risk, profiles,
        genuine_kol_swap=any(item.get("chain_verified") for item in verified),
        checked_at=int(datetime.now(UTC).timestamp()),
    )
    return {
        "schema": "debot4.bsc_gmgn_kol_audit.v2",
        "address": token, "name": candidate["name"], "symbol": candidate["symbol"],
        "market": {key: candidate.get(key) for key in (
            "window_start", "window_end_exclusive", "created_at", "first_trade_at",
            "initial_fdv_usd", "peak_at", "approx_peak_fdv_usd", "peak_multiple",
            "precision", "current_kols", "max_kols",
        )},
        "status": "complete" if history.coverage_complete else "kol_history_incomplete",
        "gmgn_history_coverage_complete": history.coverage_complete,
        "gmgn_history_stop_reason": history.stop_reason,
        "gmgn_history_pages": len(history.receipts),
        "gmgn_tagged_trade_count_in_window": len(history.trades),
        "gmgn_tagged_buy_count_in_window": len(buys),
        "verified_kol_buys": verified,
        "wallet_profile_errors": profile_errors,
        "gmgn_risk": asdict(risk),
        "manipulation": asdict(manipulation),
        "provider_receipts": (*history.receipts, risk.receipt),
    }


def _verify_swaps(trades: tuple, candidate: dict[str, object]) -> list[dict[str, object]]:
    rows = []
    with PublicBscRpcClient() as rpc:
        for trade in trades:
            row: dict[str, object] = {"provider_trade": asdict(trade)}
            try:
                swap = rpc.verify_token_buy(
                    trade.transaction_hash, trade.wallet, trade.token_address,
                )
                row.update({
                    "chain_verified": True, "rpc_swap": asdict(swap),
                    "buy_fdv_usd_proxy": str(
                        trade.price_usd * Decimal(str(candidate["total_supply"])),
                    ),
                    "before_market_peak": trade.timestamp < int(candidate["peak_at"]),
                })
            except Exception as exc:
                row.update({"chain_verified": False, "chain_error_type": type(exc).__name__})
            rows.append(row)
    return rows


def _profiles(wallets: tuple[str, ...]) -> tuple[tuple, tuple[dict[str, str], ...]]:
    profiles, errors = [], []
    with PublicGmgnWalletClient() as client:
        for wallet in wallets:
            try:
                profiles.append(client.fetch_profile("bsc", wallet))
            except Exception as exc:
                errors.append({"wallet": wallet, "error_type": type(exc).__name__})
    return tuple(profiles), tuple(errors)


def _candidates(path: Path) -> tuple[dict[str, object], ...]:
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return tuple(sorted(
        (
            row for row in rows
            if row.get("status") == "complete"
            and row.get("meets_peak_threshold") is True
            and int(row.get("max_kols") or 0) > 0
            and row.get("window_start") is not None
        ),
        key=lambda row: (int(row["created_at"]), str(row["address"])),
    ))


def _completed(handle) -> set[str]:
    handle.seek(0)
    return {
        str(row["address"])
        for line in handle if line.strip()
        if (row := json.loads(line)).get("status") in {"complete", "kol_history_incomplete"}
    }


def _append(handle, row: dict[str, object]) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(
        json_value(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n")
    handle.flush()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--observations", default="bsc_observations.jsonl")
    parser.add_argument("--output", default="bsc_gmgn_kol_audit_v2.jsonl")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--limit", type=int, default=10_000)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.offset < 0 or args.limit <= 0 or not 1 <= args.workers <= 8:
        parser.error("invalid bounded audit arguments")
    return args


if __name__ == "__main__":
    main()
