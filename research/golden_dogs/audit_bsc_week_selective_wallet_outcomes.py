#!/usr/bin/env python3
"""Audit point-in-time 24h outcomes for every mature selective-wallet buy."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.wallet_outcome import assess_wallet_buy_outcome


ROOT = Path(__file__).resolve().parent
BUYS = ROOT / "bsc_week_selective_wallet_buys.jsonl"
OUTPUT = ROOT / "bsc_week_selective_wallet_outcomes.jsonl"
SUMMARY = ROOT / "bsc_week_selective_wallet_outcomes_summary.json"
INTERVAL_SECONDS = 300
HORIZON_SECONDS = 86_400
SCHEMA = "debot4.bsc_week_selective_wallet_outcome.v2"


def main() -> None:
    all_buys = tuple(_jsonl(BUYS))
    mature = tuple(row for row in all_buys if row["outcome_mature_as_of_signal"])
    rows = _cache(mature)
    missing = tuple(row for row in mature if _key(row) not in rows)
    with ThreadPoolExecutor(max_workers=6) as executor:
        jobs = {executor.submit(_assess, buy): buy for buy in missing}
        for index, future in enumerate(as_completed(jobs), 1):
            buy = jobs[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    **_locator(buy), "status": "error",
                    "error_type": type(exc).__name__,
                }
            rows[_key(buy)] = row
            write_jsonl(OUTPUT, _ordered(rows.values()))
            print(
                f"{index}/{len(missing)} {buy['x_handle']} "
                f"{buy['token_address']}: {row['status']}", flush=True,
            )
    ordered = _ordered(rows.values())
    if len(ordered) != len(mature):
        raise RuntimeError("mature selective-wallet outcomes are incomplete")
    write_jsonl(OUTPUT, ordered)
    write_json(SUMMARY, _summary(ordered, all_buys))


def _assess(buy):
    end = int(buy["buy_at"]) + HORIZON_SECONDS
    with PublicDeBotClient(timeout_seconds=30, attempts=3) as client:
        market = client.fetch_market(
            "bsc", str(buy["token_address"]), interval_seconds=INTERVAL_SECONDS,
            limit=1_000, end=end,
        )
    supply = market.total_supply or _decimal(buy["provider_total_supply"])
    assessment = assess_wallet_buy_outcome(
        buy_at=int(buy["buy_at"]), signal_at=int(buy["signal_at"]),
        buy_price_usd=_decimal(buy["buy_price_usd"]), total_supply=supply,
        candles=market.candles, horizon_seconds=HORIZON_SECONDS,
        interval_seconds=INTERVAL_SECONDS,
    )
    return {
        **_locator(buy), "status": "complete", "assessment": asdict(assessment),
        "market_window_start": int(buy["buy_at"]),
        "market_window_end_exclusive": end,
        "market_candle_count": len(market.candles),
        "market_receipt": asdict(market.receipt),
        "supply_source": (
            "debot_current_total_supply_proxy" if market.total_supply is not None
            else "gmgn_activity_current_total_supply_proxy"
        ),
    }


def _cache(buys):
    expected = {
        _key(row): (int(row["buy_at"]), int(row["buy_at"]) + HORIZON_SECONDS)
        for row in buys
    }
    result = {}
    for row in _jsonl(OUTPUT) if OUTPUT.exists() else ():
        key = _key(row)
        bounds = expected.get(key)
        if (
            row.get("schema") == SCHEMA and row.get("status") == "complete"
            and bounds == (
                int(row.get("market_window_start", 0)),
                int(row.get("market_window_end_exclusive", 0)),
            )
        ):
            result[key] = row
    return result


def _summary(rows, all_buys):
    complete = tuple(row for row in rows if row["status"] == "complete")
    wallets = sorted({str(row["wallet"]) for row in all_buys})
    per_wallet = []
    for wallet in wallets:
        activity = tuple(row for row in all_buys if row["wallet"] == wallet)
        mature = tuple(row for row in complete if row["wallet"] == wallet)
        measurable = tuple(row for row in mature if row["assessment"]["measurable"])
        hits = sum(row["assessment"]["hit"] is True for row in measurable)
        rate = hits / len(measurable) if measurable else None
        per_wallet.append({
            "wallet": wallet, "x_handle": activity[0]["x_handle"],
            "activity_unique_tokens": len(activity), "mature_tokens": len(mature),
            "measurable_tokens": len(measurable), "hits": hits, "hit_rate": rate,
            "minimum_10_mature_tokens": len(measurable) >= 10,
            "minimum_20pct_hit_rate": rate is not None and rate >= .2,
            "skill_screen_pass": len(measurable) >= 10 and rate is not None and rate >= .2,
        })
    return {
        "schema": "debot4.bsc_week_selective_wallet_outcomes_summary.v2",
        "wallet_count": len(wallets), "activity_token_count": len(all_buys),
        "mature_outcome_count": len(rows), "complete_outcome_count": len(complete),
        "measurable_outcome_count": sum(row["assessment"]["measurable"] for row in complete),
        "hit_count": sum(row["assessment"]["hit"] is True for row in complete),
        "skill_screen_pass_count": sum(row["skill_screen_pass"] for row in per_wallet),
        "wallet_assessments": tuple(per_wallet),
        "source_sha256": {BUYS.name: hashlib.sha256(BUYS.read_bytes()).hexdigest()},
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "warnings": (
            "Only outcomes fully mature before each wallet's first winning-token appearance count.",
            "Each wallet-token has its own 24h request; 5m highs exclude the partial buy candle and use a current-supply FDV proxy.",
            "A skill-screen pass is not KOL status until point-in-time identity and control-universe precision are proven.",
        ),
    }


def _locator(row):
    return {key: row[key] for key in (
        "wallet", "x_handle", "signal_at", "buy_at", "token_address",
        "transaction_hash", "buy_price_usd", "provider_total_supply",
    )} | {"schema": SCHEMA}


def _key(row):
    return str(row["wallet"]), str(row["token_address"])


def _ordered(rows):
    return sorted(rows, key=lambda row: (
        str(row["wallet"]), int(row["buy_at"]), str(row["token_address"]),
    ))


def _decimal(value):
    return None if value is None else Decimal(str(value))


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
