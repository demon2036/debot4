#!/usr/bin/env python3
"""Audit attributed BSC KOL wallets against fixed-window market candidates."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient
from debot4.v6.golden_dogs.gmgn_kol_adapter import provider_buy_from_gmgn
from debot4.v6.golden_dogs.gmgn_public import PublicGmgnClient
from debot4.v6.golden_dogs.gmgn_trade_history import fetch_kol_trades_in_window
from debot4.v6.golden_dogs.gmgn_wallet_activity import PublicGmgnWalletActivityClient
from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient
from debot4.v6.golden_dogs.kol_identity import LOOKONCHAIN_BSC_TRADERS
from debot4.v6.golden_dogs.manipulation import assess_manipulation
from debot4.v6.golden_dogs.qualification import qualify_golden_dog
from debot4.v6.golden_dogs.research_scope import CHAIN_BOUNDS
from debot4.v6.golden_dogs.serialization import (
    json_value, observation_from_mapping, write_json, write_jsonl,
)
from debot4.v6.golden_dogs.x_binding import WalletXIdentity, assess_x_binding
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    candidates = _candidates()
    period_start, period_end = (int(item.timestamp()) for item in CHAIN_BOUNDS["bsc"])
    cases, wallets = [], []
    for identity in LOOKONCHAIN_BSC_TRADERS:
        assert identity.wallet is not None
        profile = _profile(identity.wallet)
        x_observation = XProfileClient().fetch_observation(identity.handle)
        binding = assess_x_binding(WalletXIdentity(
            wallet=identity.wallet, provider_activity_handle=profile.x_handle,
            public_profile_handle=profile.public_x_handle,
            stat_profile_handle=profile.stat_x_handle,
            provider_bound=profile.x_bound,
            fxtwitter_handle=x_observation.profile.handle,
            fxtwitter_user_id=x_observation.profile.user_id,
        ))
        with PublicGmgnWalletActivityClient() as client:
            activity = client.fetch_history(identity.wallet, period_start, period_end)
        buys = tuple(item for item in activity.activities if item.event == "buy")
        matches = tuple(item for item in buys if item.token_address in candidates)
        wallets.append({
            "schema": "debot4.known_kol_wallet_period.v1",
            "handle": identity.handle, "wallet": identity.wallet,
            "identity": asdict(identity), "gmgn_profile": asdict(profile),
            "x_profile": asdict(x_observation), "x_binding": asdict(binding),
            "period_start": period_start, "period_end_exclusive": period_end,
            "activity_coverage_complete": activity.coverage_complete,
            "activity_stop_reason": activity.stop_reason,
            "activity_pages": len(activity.receipts),
            "activity_rows": len(activity.activities), "buy_rows": len(buys),
            "buy_transactions": len({item.transaction_hash for item in buys}),
            "unique_tokens_bought": len({item.token_address for item in buys}),
            "market_candidate_buy_rows": len(matches),
            "market_candidate_addresses": sorted({item.token_address for item in matches}),
            "receipts": (*activity.receipts, *profile.receipts),
        })
        for token in sorted({item.token_address for item in matches}):
            try:
                case = _audit_case(
                    identity.handle, identity.wallet, profile, candidates[token],
                )
            except Exception as exc:
                case = {
                    "schema": "debot4.known_kol_market_case.v1",
                    "handle": identity.handle, "wallet": identity.wallet,
                    "observation": candidates[token], "status": "error",
                    "error_type": type(exc).__name__,
                }
            cases.append(case)
            print(f"{identity.handle} {token} {case.get('status')}", flush=True)
    write_jsonl(ROOT / "known_kol_wallet_periods.jsonl", wallets)
    write_jsonl(ROOT / "known_kol_market_cases.jsonl", cases)
    write_json(ROOT / "known_kol_audit_summary.json", _summary(wallets, cases))


def _audit_case(handle: str, wallet: str, profile, observation) -> dict[str, object]:
    with PublicGmgnClient() as gmgn:
        history = fetch_kol_trades_in_window(
            gmgn, observation.address, observation.window_start,
            observation.window_end_exclusive,
        )
        risk = gmgn.fetch_risk("bsc", observation.address)
    trades = tuple(
        item for item in history.trades if item.event == "buy" and item.wallet == wallet
    )
    provider_buys, swaps, errors = [], [], []
    with PublicBscRpcClient() as rpc:
        for trade in trades:
            try:
                swap = rpc.verify_token_buy(trade.transaction_hash, wallet, observation.address)
                provider_buys.append(provider_buy_from_gmgn(
                    trade, swap,
                    provider_url=f"https://gmgn.ai/bsc/token/{observation.address}",
                ))
                swaps.append(swap)
            except Exception as exc:
                errors.append({"transaction_hash": trade.transaction_hash,
                               "error_type": type(exc).__name__})
    manipulation = assess_manipulation(
        risk, (profile,), genuine_kol_swap=bool(swaps),
        checked_at=int(datetime.now(UTC).timestamp()),
    )
    assessment = qualify_golden_dog(
        observation, tuple(provider_buys), manipulation,
        kol_coverage_complete=history.coverage_complete,
    )
    return {
        "schema": "debot4.known_kol_market_case.v1", "handle": handle,
        "status": "complete",
        "wallet": wallet, "observation": observation, "gmgn_trades": trades,
        "rpc_swaps": swaps, "verification_errors": errors,
        "kol_history_coverage_complete": history.coverage_complete,
        "kol_history_stop_reason": history.stop_reason,
        "kol_history_pages": len(history.receipts), "risk": risk,
        "manipulation": manipulation, "qualification": assessment,
        "provider_receipts": (*history.receipts, risk.receipt),
    }


def _profile(wallet: str):
    with PublicGmgnWalletClient() as client:
        return client.fetch_profile("bsc", wallet)


def _candidates() -> dict[str, object]:
    path = ROOT / "bsc_market_candidates.jsonl"
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    return {str(row["address"]): observation_from_mapping(row) for row in rows}


def _summary(wallets: list[dict], cases: list[dict]) -> dict[str, object]:
    complete = [item for item in cases if item.get("status") == "complete"]
    return {
        "schema": "debot4.known_kol_audit_summary.v1",
        "generated_at": datetime.now(UTC), "wallet_count": len(wallets),
        "case_count": len(cases),
        "complete_cases": len(complete), "error_cases": len(cases) - len(complete),
        "qualification_verdicts": _counts(complete, "qualification", "verdict"),
        "causal_timing_verdicts": _counts(
            complete, "qualification", "causal_timing", "verdict",
        ),
        "warning": "wallet outcomes are incomplete; no smart-wallet win rate is claimed",
    }


def _counts(rows: list[dict], *path: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value: object = json_value(row)
        for key in path:
            value = value[key]  # type: ignore[index]
        counts[str(value)] = counts.get(str(value), 0) + 1
    return dict(sorted(counts.items()))


if __name__ == "__main__":
    main()
