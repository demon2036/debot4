#!/usr/bin/env python3
"""Collect every provider-ordered buy strictly before each first 1.02x trade."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.early_trade_signals import classify_early_trade
from debot4.v6.golden_dogs.gmgn_market_history import fetch_market_trades_in_window
from debot4.v6.golden_dogs.gmgn_market_trades import PublicGmgnMarketTradeClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.trade_price_timing import (
    classify_trade_signal,
    find_transaction_price_crossing,
)


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bsc_week_trade_price_evidence.jsonl"
UNIVERSE = ROOT / "bsc_universe.jsonl"
OUTPUT = ROOT / "bsc_week_pre_breakout_buys.jsonl"
WALLETS = ROOT / "bsc_week_pre_breakout_wallets.jsonl"


def main() -> None:
    args = _args()
    source = _jsonl(SOURCE)
    target_addresses = {str(row["address"]) for row in source}
    tokens = {
        str(row["address"]): row for row in _jsonl(UNIVERSE)
        if str(row["address"]) in target_addresses
    }
    if len(source) != 32 or len(target_addresses) != 13 or set(tokens) != target_addresses:
        raise RuntimeError("pre-breakout collection requires all 13 targets and 32 waves")
    rows = []
    with PublicGmgnMarketTradeClient(timeout_seconds=40, attempts=3) as client:
        for wave in source:
            crossing_source = _crossing(wave, "1.02")
            if crossing_source is None:
                raise RuntimeError("every target wave requires a first 1.02x trade")
            start = int(wave["window_start"])
            history = fetch_market_trades_in_window(
                client, str(wave["address"]), start,
                int(crossing_source["occurred_at"]) + 2,
                max_pages=args.max_pages, page_delay_seconds=args.request_delay,
            )
            crossing = find_transaction_price_crossing(
                history.trades,
                Decimal(str(crossing_source["threshold_price_usd"])),
                not_before=start,
            )
            _require_same_crossing(crossing_source, crossing)
            creator = str(tokens[str(wave["address"])]["creator_address"])
            buys = tuple(
                _buy(trade, crossing, start, creator)
                for trade in history.trades if trade.event == "buy"
                and classify_trade_signal(
                    trade, crossing, baseline_established_at=start,
                ).strict_advance
            )
            rows.append({
                "schema": "debot4.bsc_week_pre_breakout_buys.v1",
                "label": wave["label"], "address": wave["address"],
                "wave_number": wave["wave_number"], "creator_address": creator,
                "launchpad": tokens[str(wave["address"])]["launchpad"],
                "created_at": tokens[str(wave["address"])]["created_at"],
                "baseline_established_at": start,
                "first_1_02_crossing": asdict(crossing),
                "coverage_complete": history.coverage_complete,
                "stop_reason": history.stop_reason,
                "strict_pre_1_02_buy_count": len(buys), "buys": buys,
                "receipts": history.receipts,
            })
            print(
                f"{wave['label']} w{wave['wave_number']}: "
                f"buys={len(buys)} complete={history.coverage_complete}"
            )
    if any(row["coverage_complete"] is not True for row in rows):
        raise RuntimeError("GMGN did not prove complete pre-breakout coverage")
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    wallet_rows = _wallet_rows(rows)
    write_jsonl(OUTPUT, rows)
    write_jsonl(WALLETS, wallet_rows)
    write_json(
        ROOT / "bsc_week_pre_breakout_buys_summary.json",
        _summary(rows, wallet_rows),
    )


def _buy(trade, crossing, baseline_at, creator):
    timing = classify_trade_signal(
        trade, crossing, baseline_established_at=baseline_at,
    )
    provider = classify_early_trade(trade)
    return {
        "wallet": trade.wallet, "occurred_at": trade.timestamp,
        "transaction_hash": trade.transaction_hash,
        "amount_usd": trade.amount_usd, "price_usd": trade.price_usd,
        "token_amount": trade.token_amount,
        "provider_sequence": trade.provider_sequence,
        "seconds_to_1_02": timing.seconds_to_motion,
        "sequence_gap": timing.sequence_gap,
        "name": trade.name, "x_handle": trade.x_handle,
        "wallet_tags": trade.wallet_tags, "token_tags": trade.token_tags,
        "event_tags": trade.event_tags,
        "provider_class": provider.classification,
        "provider_matched_tags": provider.matched_tags,
        "creator_match": trade.wallet == creator,
        "as_of_skill_qualified": False,
        "qualification_reason": "winner-only observation has no prior control-adjusted skill proof",
    }


def _wallet_rows(rows):
    wallets: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        for buy in row["buys"]:
            wallets.setdefault(str(buy["wallet"]), []).append({
                "label": row["label"], "address": row["address"],
                "wave_number": row["wave_number"],
                "occurred_at": buy["occurred_at"],
                "transaction_hash": buy["transaction_hash"],
                "amount_usd": buy["amount_usd"],
                "creator_match": buy["creator_match"],
            })
    result = []
    for wallet, observations in wallets.items():
        observations.sort(key=lambda item: (
            int(item["occurred_at"]), str(item["transaction_hash"]),
        ))
        result.append({
            "schema": "debot4.bsc_week_pre_breakout_wallet.v1",
            "wallet": wallet, "buy_count": len(observations),
            "wave_count": len({
                (item["address"], item["wave_number"]) for item in observations
            }),
            "target_count": len({item["address"] for item in observations}),
            "creator_match_count": sum(
                item["creator_match"] is True for item in observations
            ),
            "observations": observations,
            "retrospective_repeat_candidate": len({
                (item["address"], item["wave_number"]) for item in observations
            }) >= 2,
            "as_of_skill_qualified": False,
            "warning": "Selected winners alone cannot establish wallet precision or skill.",
        })
    return sorted(result, key=lambda item: str(item["wallet"]))


def _require_same_crossing(expected, observed) -> None:
    if observed is None or any((
        observed.transaction_hash != expected["transaction_hash"],
        observed.occurred_at != int(expected["occurred_at"]),
        observed.provider_sequence != expected.get("provider_sequence"),
    )):
        raise RuntimeError("refetched 1.02x crossing differs from frozen evidence")


def _crossing(row, multiple):
    return next(
        (item["crossing"] for item in row["transaction_price_ladder"]
         if item["multiple"] == multiple), None,
    )


def _summary(rows, wallets):
    return {
        "schema": "debot4.bsc_week_pre_breakout_buys_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "strict_pre_1_02_buy_count": sum(
            row["strict_pre_1_02_buy_count"] for row in rows
        ),
        "unique_wallet_count": len(wallets),
        "repeat_wave_wallet_count": sum(
            row["retrospective_repeat_candidate"] is True for row in wallets
        ),
        "repeat_target_wallet_count": sum(row["target_count"] >= 2 for row in wallets),
        "creator_match_buy_count": sum(
            buy["creator_match"] is True for row in rows for buy in row["buys"]
        ),
        "as_of_skill_qualified_wallet_count": 0,
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (SOURCE, UNIVERSE, OUTPUT, WALLETS)
        },
        "warnings": (
            "Provider order is evidence discovery, not observed production latency.",
            "Same-block buys require RPC position checks before actionability claims.",
            "This winner-only set cannot prove precision, profit, or wallet skill.",
        ),
    }


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--request-delay", type=float, default=0.10)
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 500 or not 0 <= args.request_delay <= 5:
        parser.error("invalid GMGN collection bounds")
    return args


if __name__ == "__main__":
    main()
