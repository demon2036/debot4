#!/usr/bin/env python3
"""Collect full local trade flow and refine all wave motion times to seconds."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.early_trade_signals import (
    EarlyTradeSignalClass,
    classify_early_trade,
)
from debot4.v6.golden_dogs.gmgn_market_history import (
    fetch_market_trades_in_window,
    trade_evidence_window_end,
)
from debot4.v6.golden_dogs.gmgn_market_trades import PublicGmgnMarketTradeClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.trade_microstructure import (
    find_price_ladder,
    summarize_pre_crossing_buy_flow,
)
from debot4.v6.golden_dogs.trade_price_timing import (
    classify_trade_signal,
    find_transaction_price_crossing,
)


ROOT = Path(__file__).resolve().parent
MINUTE = ROOT / "bsc_week_minute_wave_replays.jsonl"
FIVE_MINUTE = ROOT / "bsc_week_wave_replays.jsonl"
PARTIAL = ROOT / "bsc_week_trade_price_evidence.partial.jsonl"


def main() -> None:
    args = _args()
    waves = _jsonl(MINUTE)
    replays = {str(row["address"]): row for row in _jsonl(FIVE_MINUTE)}
    rows = _jsonl(PARTIAL) if args.resume and PARTIAL.exists() else []
    completed = {
        (str(row["address"]), int(row["wave_number"])) for row in rows
    }
    with PublicGmgnMarketTradeClient(timeout_seconds=40, attempts=3) as client:
        for wave in waves:
            key = (str(wave["address"]), int(wave["wave_number"]))
            if key in completed:
                print(f"{wave['label']} w{wave['wave_number']}: resumed")
                continue
            boundary = wave["boundary"]
            motion = boundary["motion"]
            if motion is None:
                raise RuntimeError("all target waves require a 1.2x motion boundary")
            replay = replays[str(wave["address"])]
            fresh = _fresh_start(replay, int(wave["wave_number"]))
            baseline_at = int(boundary["baseline_established_at"])
            motion_bar = int(motion["crossing_before"])
            breakout = boundary["breakout"]
            start = baseline_at
            end = trade_evidence_window_end(
                motion_crossing_before=motion_bar,
                breakout_crossing_end_exclusive=(
                    int(breakout["crossing_end_exclusive"])
                    if breakout else None
                ),
                wave_end_exclusive=int(boundary["wave_end_exclusive"]),
            )
            history = fetch_market_trades_in_window(
                client, str(wave["address"]), start, end, max_pages=args.max_pages,
                page_delay_seconds=args.request_delay,
            )
            crossing = find_transaction_price_crossing(
                history.trades, Decimal(str(motion["threshold_price_usd"])),
                not_before=baseline_at,
            )
            ladder = find_price_ladder(
                history.trades,
                Decimal(str(boundary["baseline_price_usd"])),
                baseline_established_at=baseline_at,
            )
            candidates = tuple(
                _candidate(trade, crossing, boundary)
                for trade in history.trades
                if trade.event == "buy"
                and classify_early_trade(trade).classification
                in {
                    EarlyTradeSignalClass.PROVIDER_SMART_CANDIDATE,
                    EarlyTradeSignalClass.KOL_TAGGED,
                }
            )
            rows.append({
                "schema": "debot4.bsc_week_trade_price_audit.v1",
                "label": wave["label"], "address": wave["address"],
                "wave_number": wave["wave_number"],
                "window_start": start, "window_end_exclusive": end,
                "fresh_signal_start": fresh,
                "scan_rule": "baseline_established_at_to_breakout_candle_plus_60s",
                "coverage_complete": history.coverage_complete,
                "stop_reason": history.stop_reason,
                "trade_count": len(history.trades),
                "buy_count": sum(item.event == "buy" for item in history.trades),
                "motion_threshold_price_usd": motion["threshold_price_usd"],
                "transaction_motion_crossing": asdict(crossing) if crossing else None,
                "transaction_price_ladder": tuple(
                    _ladder_step(step, history.trades, baseline_at)
                    for step in ladder
                ),
                "pre_motion_buy_flow": (
                    tuple(asdict(item) for item in summarize_pre_crossing_buy_flow(
                        history.trades, crossing,
                        baseline_established_at=baseline_at,
                    )) if crossing else ()
                ),
                "provider_candidates": candidates,
                "receipt_sha256s": tuple(item.sha256 for item in history.receipts),
                "receipts": history.receipts,
            })
            rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
            write_jsonl(PARTIAL, rows)
            print(
                f"{wave['label']} w{wave['wave_number']}: trades={len(history.trades)} "
                f"pages={len(history.receipts)} complete={history.coverage_complete} "
                f"cross={crossing.occurred_at if crossing else None}"
            )
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 trade-price rows, got {len(rows)}")
    output = ROOT / "bsc_week_trade_price_evidence.jsonl"
    write_jsonl(output, rows)
    write_json(ROOT / "bsc_week_trade_price_evidence_summary.json", _summary(rows, output))
    PARTIAL.unlink(missing_ok=True)


def _candidate(trade, crossing, boundary):
    signal = classify_early_trade(trade)
    timing = classify_trade_signal(
        trade, crossing,
        baseline_established_at=int(boundary["baseline_established_at"]),
    )
    return {
        "wallet": trade.wallet, "occurred_at": trade.timestamp,
        "transaction_hash": trade.transaction_hash,
        "amount_usd": trade.amount_usd, "price_usd": trade.price_usd,
        "provider_sequence": trade.provider_sequence,
        "x_handle": trade.x_handle, "wallet_tags": trade.wallet_tags,
        "token_tags": trade.token_tags, "event_tags": trade.event_tags,
        "provider_class": signal.classification,
        "provider_matched_tags": signal.matched_tags,
        "provider_reasons": signal.reasons,
        "timing": asdict(timing),
        "qualified_online_signal": False,
        "qualification_reason": (
            "provider_label_requires_as_of_wallet_or_kol_history"
        ),
    }


def _ladder_step(step, trades, baseline_at):
    crossing = step.crossing
    return {
        "multiple": step.multiple,
        "crossing": asdict(crossing) if crossing else None,
        "pre_crossing_buy_flow": (
            tuple(asdict(item) for item in summarize_pre_crossing_buy_flow(
                trades, crossing, baseline_established_at=baseline_at,
            )) if crossing else ()
        ),
    }


def _summary(rows, output):
    complete = tuple(row for row in rows if row["coverage_complete"] is True)
    strict = tuple(
        row for row in complete
        if any(item["timing"]["strict_advance"] for item in row["provider_candidates"])
    )
    return {
        "schema": "debot4.bsc_week_trade_price_evidence_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows), "complete_local_window_count": len(complete),
        "transaction_crossing_count": sum(
            row["transaction_motion_crossing"] is not None for row in rows
        ),
        "price_ladder_complete_count": sum(
            len(row.get("transaction_price_ladder", ())) == 4
            and all(item["crossing"] is not None
                    for item in row["transaction_price_ladder"])
            for row in rows
        ),
        "provider_candidate_strict_wave_upper_bound": len(strict),
        "qualified_online_signal_wave_count": 0,
        "scan_rule": "baseline_established_at_to_breakout_candle_plus_60s",
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (MINUTE, FIVE_MINUTE, output)
        },
        "warnings": (
            "Only complete baseline-to-motion windows support negative conclusions.",
            "Provider smart/KOL labels are discovery leads, not qualified signals.",
            "The baseline and winning wave are retrospective; candidates require an "
            "as-of-time history gate before they can count as online capture.",
            "A transaction earlier in the same block as motion is not post-confirmation "
            "actionable; block-order verification is a separate gate.",
        ),
    }


def _fresh_start(replay, number):
    effective = [item for item in replay["completed_swings"] if item["effective"]]
    return (
        int(replay["created_at"])
        if number == 1 else int(effective[number - 2]["reset_at"])
    )


def _jsonl(path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=500)
    parser.add_argument("--request-delay", type=float, default=0.20)
    parser.add_argument("--no-resume", action="store_false", dest="resume")
    args = parser.parse_args()
    if not 1 <= args.max_pages <= 500:
        parser.error("max pages must be between one and 500")
    if not 0 <= args.request_delay <= 5:
        parser.error("request delay must be between zero and five seconds")
    return args


if __name__ == "__main__":
    main()
