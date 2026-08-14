#!/usr/bin/env python3
"""Collect receipted 1m bars and refine all 32 reviewed BSC waves."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.market_audit import fetch_window_bars
from debot4.v6.golden_dogs.minute_breakout import (
    MAIN_BREAKOUT_MULTIPLE,
    PRICE_MOTION_MULTIPLE,
    analyze_minute_wave,
)
from debot4.v6.golden_dogs.models import TokenSeed
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
REPLAYS = ROOT / "bsc_week_wave_replays.jsonl"
UNIVERSE = ROOT / "bsc_universe.jsonl"
INTERVAL_SECONDS = 60
SOURCE_WAVE_SECONDS = 300


def main() -> None:
    replays = _read_jsonl(REPLAYS)
    seeds = _load_seeds(UNIVERSE, {str(row["address"]) for row in replays})
    wave_rows: list[dict[str, object]] = []
    receipt_rows: list[dict[str, object]] = []
    with PublicDeBotClient(timeout_seconds=40, attempts=3) as client:
        for replay in replays:
            address = str(replay["address"]).casefold()
            seed = seeds[address]
            start = int(replay["window_start"])
            end = int(replay["window_end_exclusive"])
            market = fetch_window_bars(
                client, seed, start, end, INTERVAL_SECONDS, max_pages=16,
            )
            if not market.coverage_complete or not market.candles:
                raise RuntimeError(f"incomplete 1m market evidence for {address}")
            supply = Decimal(str(replay["total_supply_proxy"]))
            if market.total_supply is None:
                raise RuntimeError(f"missing 1m supply evidence for {address}")
            receipt_hashes = tuple(item.sha256 for item in market.receipts)
            receipt_rows.append({
                "schema": "debot4.bsc_week_minute_market_receipts.v1",
                "label": replay["label"],
                "address": address,
                "interval_seconds": INTERVAL_SECONDS,
                "candle_count": len(market.candles),
                "coverage_complete": market.coverage_complete,
                "returned_total_supply": market.total_supply,
                "replay_total_supply_proxy": supply,
                "receipts": market.receipts,
            })
            effective = tuple(
                wave for wave in replay["completed_swings"] if wave["effective"]
            )
            for wave_number, wave in enumerate(effective, 1):
                wave_start = int(wave["trough_at"])
                trough_end = min(wave_start + SOURCE_WAVE_SECONDS, end)
                wave_end = min(int(wave["peak_at"]) + SOURCE_WAVE_SECONDS, end)
                boundary = analyze_minute_wave(
                    market.candles,
                    supply,
                    wave_start=wave_start,
                    trough_end_exclusive=trough_end,
                    wave_end_exclusive=wave_end,
                    interval_seconds=INTERVAL_SECONDS,
                )
                selected = tuple(
                    asdict(bar) for bar in market.candles
                    if wave_start <= bar.time < wave_end
                )
                wave_rows.append({
                    "schema": "debot4.bsc_week_minute_wave_replay.v1",
                    "label": replay["label"],
                    "address": address,
                    "wave_number": wave_number,
                    "source_5m_wave": wave,
                    "boundary": asdict(boundary),
                    "minute_bars": selected,
                    "source_receipt_sha256s": receipt_hashes,
                })
            print(
                f"{replay['label']}: 1m={len(market.candles)} "
                f"pages={len(market.receipts)} waves={len(effective)}"
            )

    wave_rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    receipt_rows.sort(key=lambda row: str(row["address"]))
    wave_path = ROOT / "bsc_week_minute_wave_replays.jsonl"
    receipt_path = ROOT / "bsc_week_minute_market_receipts.jsonl"
    write_jsonl(wave_path, wave_rows)
    write_jsonl(receipt_path, receipt_rows)
    write_json(ROOT / "bsc_week_minute_wave_replay_summary.json", {
        "schema": "debot4.bsc_week_minute_wave_replay_summary.v1",
        "target_count": len(receipt_rows),
        "wave_count": len(wave_rows),
        "coverage_complete_count": sum(
            row["coverage_complete"] is True for row in receipt_rows
        ),
        "interval_seconds": INTERVAL_SECONDS,
        "source_wave_seconds": SOURCE_WAVE_SECONDS,
        "price_motion_multiple": PRICE_MOTION_MULTIPLE,
        "main_breakout_multiple": MAIN_BREAKOUT_MULTIPLE,
        "motion_crossing_count": sum(
            row["boundary"]["motion"] is not None for row in wave_rows
        ),
        "breakout_crossing_count": sum(
            row["boundary"]["breakout"] is not None for row in wave_rows
        ),
        "source_sha256": {
            REPLAYS.name: _sha256(REPLAYS),
            UNIVERSE.name: _sha256(UNIVERSE),
            receipt_path.name: _sha256(receipt_path),
            wave_path.name: _sha256(wave_path),
        },
        "timing_warning": (
            "A high proves crossing somewhere inside its minute, not the exact "
            "second. Only evidence before crossing_before is strictly pre-crossing; "
            "evidence inside that candle is ambiguous and must not count as advance."
        ),
        "causality_warning": (
            "The 5m completed wave locates a retrospective research window. The 1m "
            "boundary describes price timing and does not itself prove an online "
            "signal, actor identity, wallet quality, or causal relationship."
        ),
    })


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _load_seeds(path: Path, wanted: set[str]) -> dict[str, TokenSeed]:
    seeds: dict[str, TokenSeed] = {}
    for row in _read_jsonl(path):
        address = str(row.get("address", "")).casefold()
        if address not in wanted:
            continue
        seeds[address] = TokenSeed(
            chain=str(row["chain"]), address=address, name=str(row["name"]),
            symbol=str(row["symbol"]), launchpad=str(row["launchpad"]),
            created_at=int(row["created_at"]),
            creator_address=row.get("creator_address"),
            rank_supply=(Decimal(str(row["rank_supply"]))
                         if row.get("rank_supply") is not None else None),
            current_kols=int(row["current_kols"]), max_kols=int(row["max_kols"]),
            social_urls=tuple(str(item) for item in row.get("social_urls", ())),
            discovered_sources=tuple(
                str(item) for item in row.get("discovered_sources", ())
            ),
        )
    missing = wanted - seeds.keys()
    if missing:
        raise RuntimeError(f"target seeds missing from universe: {len(missing)}")
    return seeds


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
