#!/usr/bin/env python3
"""Collect every unique pre-signal token bought by selective X-wallet leads."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import time

from debot4.v6.golden_dogs.gmgn_wallet_activity import (
    PublicGmgnWalletActivityClient,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
ACTIVITY = ROOT / "bsc_week_all_x_wallet_activity.jsonl"
OUTPUT = ROOT / "bsc_week_selective_wallet_buys.jsonl"
SUMMARY = ROOT / "bsc_week_selective_wallet_buys_summary.json"


def main() -> None:
    candidates = tuple(
        row for row in _jsonl(ACTIVITY)
        if row["eligible_for_outcome_denominator_audit"] is True
    )
    cache = _cache(candidates)
    rows = dict(cache)
    receipts: dict[str, tuple[str, ...]] = {}
    with PublicGmgnWalletActivityClient(timeout_seconds=30, attempts=3) as client:
        for index, candidate in enumerate(candidates, 1):
            wallet = str(candidate["wallet"])
            if wallet in cache:
                result = cache[wallet]
            else:
                result, receipts[wallet] = _collect(client, candidate)
                time.sleep(1)
            rows[wallet] = result
            write_jsonl(OUTPUT, _flatten(rows.values()))
            print(f"{index}/{len(candidates)} {candidate['x_handle']}: {len(result)} tokens", flush=True)
    flat = _flatten(rows.values())
    _validate(flat, candidates)
    write_jsonl(OUTPUT, flat)
    write_json(SUMMARY, _summary(flat, candidates, receipts))


def _collect(client, candidate):
    history = client.fetch_history(
        str(candidate["wallet"]), int(candidate["period_start"]),
        int(candidate["period_end_exclusive"]), max_pages=200,
    )
    if not history.coverage_complete:
        raise RuntimeError(f"incomplete wallet activity: {history.stop_reason}")
    buys = tuple(item for item in history.activities if item.event == "buy")
    unique: dict[str, object] = {}
    for buy in buys:
        previous = unique.get(buy.token_address)
        if previous is None or (buy.timestamp, buy.transaction_hash) < (
            previous.timestamp, previous.transaction_hash,  # type: ignore[attr-defined]
        ):
            unique[buy.token_address] = buy
    rows = tuple(
        _row(candidate, buy) for buy in sorted(
            unique.values(), key=lambda item: (item.timestamp, item.token_address),
        )
    )
    expected = int(candidate["unique_tokens_bought"])
    if len(rows) != expected or len({buy.transaction_hash for buy in buys}) != int(
        candidate["buy_transactions"]
    ):
        raise RuntimeError("wallet activity denominator changed during outcome collection")
    return rows, tuple(receipt.sha256 for receipt in history.receipts)


def _row(candidate, buy):
    return {
        "schema": "debot4.bsc_week_selective_wallet_buy.v1",
        "wallet": candidate["wallet"], "x_handle": candidate["x_handle"],
        "signal_at": candidate["signal_at"], "buy_at": buy.timestamp,
        "token_address": buy.token_address,
        "transaction_hash": buy.transaction_hash,
        "buy_price_usd": buy.price_usd,
        "provider_total_supply": buy.token_total_supply,
        "outcome_mature_as_of_signal": buy.timestamp + 86_400 <= int(candidate["signal_at"]),
    }


def _cache(candidates):
    expected = {
        (str(row["wallet"]), int(row["signal_at"])): int(row["unique_tokens_bought"])
        for row in candidates
    }
    grouped: dict[str, list[dict]] = {}
    for row in _jsonl(OUTPUT) if OUTPUT.exists() else ():
        grouped.setdefault(str(row["wallet"]), []).append(row)
    return {
        wallet: tuple(items) for wallet, items in grouped.items()
        if expected.get((wallet, int(items[0]["signal_at"]))) == len(items)
    }


def _flatten(groups):
    return sorted(
        (item for group in groups for item in group),
        key=lambda row: (str(row["wallet"]), int(row["buy_at"]), str(row["token_address"])),
    )


def _validate(rows, candidates):
    if len(rows) != sum(int(row["unique_tokens_bought"]) for row in candidates):
        raise RuntimeError("selective-wallet denominator is incomplete")
    keys = {(row["wallet"], row["token_address"]) for row in rows}
    if len(keys) != len(rows):
        raise RuntimeError("selective-wallet denominator has duplicate tokens")


def _summary(rows, candidates, receipts):
    return {
        "schema": "debot4.bsc_week_selective_wallet_buys_summary.v1",
        "wallet_count": len(candidates), "unique_wallet_token_count": len(rows),
        "mature_as_of_signal_count": sum(row["outcome_mature_as_of_signal"] for row in rows),
        "buy_price_present_count": sum(row["buy_price_usd"] is not None for row in rows),
        "supply_present_count": sum(row["provider_total_supply"] is not None for row in rows),
        "wallet_counts": tuple({
            "wallet": candidate["wallet"], "x_handle": candidate["x_handle"],
            "unique_tokens": sum(row["wallet"] == candidate["wallet"] for row in rows),
        } for candidate in candidates),
        "fresh_receipt_sha256": receipts,
        "source_sha256": {ACTIVITY.name: hashlib.sha256(ACTIVITY.read_bytes()).hexdigest()},
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "warning": "Maturity is censored at each wallet's first observed winning-token buy; later outcomes cannot qualify the wallet retroactively.",
    }


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


if __name__ == "__main__":
    main()
