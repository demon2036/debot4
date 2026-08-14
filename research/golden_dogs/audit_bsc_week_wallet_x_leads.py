#!/usr/bin/env python3
"""Verify X-bound pre-breakout wallets and their pre-signal activity denominator."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.gmgn_wallet_activity import (
    PublicGmgnWalletActivityClient,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.wallet_signal import (
    WalletSignalHistory, assess_wallet_signal,
)
from debot4.v6.golden_dogs.x_binding import WalletXIdentity, assess_x_binding
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
PROFILES = ROOT / "bsc_week_pre_breakout_wallet_profiles.jsonl"
BUYS = ROOT / "bsc_week_pre_breakout_buys.jsonl"
OUTPUT = ROOT / "bsc_week_wallet_x_leads.jsonl"
PERIOD_SECONDS = 7 * 86_400


def main() -> None:
    candidates = _candidates()
    cached = {
        str(row["wallet"]): row for row in _jsonl(OUTPUT)
    } if OUTPUT.exists() else {}
    rows = [cached.get(str(row["wallet"])) or _audit(row) for row in candidates]
    rows.sort(key=lambda row: str(row["wallet"]))
    write_jsonl(OUTPUT, rows)
    write_json(ROOT / "bsc_week_wallet_x_leads_summary.json", _summary(rows))


def _audit(row):
    profile = row["profile"]
    signal_at = min(int(item["occurred_at"]) for item in row["observations"])
    history = _history(str(row["wallet"]), signal_at)
    binding = _binding(row)
    signal = WalletSignalHistory(
        wallet=str(row["wallet"]), x_handle=profile["x_handle"],
        period_start=signal_at - PERIOD_SECONDS,
        period_end_exclusive=signal_at,
        unique_tokens_bought=history["unique_tokens_bought"],
        buy_transactions=history["buy_transactions"],
        pre_peak_gold_hits=0,
        outcomes_complete=False,
        activity_coverage_complete=history["coverage_complete"],
        provider_risk_tags=tuple(profile["tags"]),
    )
    assessment = assess_wallet_signal(signal)
    return {
        "schema": "debot4.bsc_week_wallet_x_lead.v1",
        "wallet": row["wallet"], "signal_at": signal_at,
        "observations": row["observations"],
        "provider_profile": profile,
        "x_binding": binding,
        "pre_signal_activity": history,
        "wallet_signal_assessment": asdict(assessment),
        "as_of_identity_qualified": False,
        "as_of_skill_qualified": False,
        "warnings": (
            "Current provider/X agreement cannot be backdated to signal time.",
            "Outcomes for every token in the denominator remain unmeasured.",
        ),
    }


def _history(wallet, end):
    with PublicGmgnWalletActivityClient(timeout_seconds=30, attempts=3) as client:
        result = client.fetch_history(
            wallet, end - PERIOD_SECONDS, end, max_pages=200,
        )
    buys = tuple(item for item in result.activities if item.event == "buy")
    return {
        "period_start": end - PERIOD_SECONDS,
        "period_end_exclusive": end,
        "coverage_complete": result.coverage_complete,
        "stop_reason": result.stop_reason,
        "page_count": len(result.receipts),
        "activity_count": len(result.activities),
        "buy_transactions": len({item.transaction_hash for item in buys}),
        "unique_tokens_bought": len({item.token_address for item in buys}),
        "receipt_sha256": tuple(item.sha256 for item in result.receipts),
    }


def _binding(row):
    profile = row["profile"]
    handle = str(profile["x_handle"])
    try:
        observed = XProfileClient().fetch_observation(handle)
        result = assess_x_binding(WalletXIdentity(
            wallet=str(row["wallet"]),
            provider_activity_handle=_trade_handle(row, handle),
            public_profile_handle=profile["public_x_handle"],
            stat_profile_handle=profile["stat_x_handle"],
            provider_bound=profile["x_bound"],
            fxtwitter_handle=observed.profile.handle,
            fxtwitter_user_id=observed.profile.user_id,
        ))
        return {
            "status": "complete", "assessment": asdict(result),
            "x_profile": asdict(observed.profile),
            "source_url": observed.source_url,
            "payload_sha256": observed.sha256,
            "response_bytes": observed.response_bytes,
        }
    except Exception as exc:
        return {
            "status": "error", "error_type": type(exc).__name__,
            "assessment": None,
        }


def _trade_handle(row, fallback):
    historical = {
        str(item.get("x_handle") or "").casefold(): item.get("x_handle")
        for wave in _jsonl(BUYS) for item in wave["buys"]
        if item["wallet"] == row["wallet"] and item.get("x_handle")
    }
    return historical.get(fallback.casefold())


def _candidates():
    rows = tuple(
        row for row in _jsonl(PROFILES)
        if row["status"] == "complete"
        and row["profile"]["x_bound"] is True
        and row["profile"]["x_handle"]
    )
    if len(rows) != 5:
        raise RuntimeError("wallet/X lead audit requires exactly five candidates")
    return rows


def _summary(rows):
    frequencies = tuple({
        "wallet": row["wallet"],
        "x_handle": row["provider_profile"]["x_handle"],
        "unique_tokens_bought_7d": row["pre_signal_activity"]["unique_tokens_bought"],
        "buy_transactions_7d": row["pre_signal_activity"]["buy_transactions"],
    } for row in rows)
    return {
        "schema": "debot4.bsc_week_wallet_x_leads_summary.v1",
        "candidate_count": len(rows),
        "current_x_binding_pass_count": sum(
            (row["x_binding"].get("assessment") or {}).get("verdict") == "PASS"
            for row in rows
        ),
        "current_x_profile_error_count": sum(
            row["x_binding"]["status"] == "error" for row in rows
        ),
        "complete_pre_signal_activity_count": sum(
            row["pre_signal_activity"]["coverage_complete"] for row in rows
        ),
        "as_of_identity_qualified_count": 0,
        "as_of_skill_qualified_count": 0,
        "pre_signal_frequencies": frequencies,
        "generated_at": datetime.now(timezone.utc),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (PROFILES, BUYS, OUTPUT)
        },
        "warning": (
            "Winner-selected appearances and current X bindings do not establish "
            "historical identity, precision, or KOL status."
        ),
    }


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
