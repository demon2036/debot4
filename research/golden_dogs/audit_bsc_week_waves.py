#!/usr/bin/env python3
"""Persist a reproducible 5m replay for the 13 reviewed BSC contracts."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path

from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.market_audit import fetch_window_bars
from debot4.v6.golden_dogs.market_waves import (
    MIN_WAVE_MULTIPLE,
    MIN_WAVE_PEAK_FDV_USD,
    WAVE_RESET_FRACTION,
    replay_market_waves,
)
from debot4.v6.golden_dogs.models import TokenSeed
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
WINDOW_START = 1_785_974_400  # 2026-08-06T00:00:00Z
WINDOW_END_EXCLUSIVE = 1_786_579_200  # 2026-08-13T00:00:00Z
INTERVAL_SECONDS = 300
TARGETS = (
    ("CETS", "0xb0c2ab5af4028461ace3f6e1c33a4ee1404e7777"),
    ("Asian games", "0x31d19b3633ebdb60dc9d690b3e9eb1fff61a7777"),
    ("bStocks", "0x244b112cf746e62a5df723cbde9906a6defd7777"),
    ("BOT", "0xbcad9b1b85af1cd81437252bf50b87235c0b7777"),
    ("fourclub", "0x530227c569960ba0fa345f19cf743a477f147777"),
    ("bNS", "0xdc5e4d5f157482059126eb15d84f2ff9368b7777"),
    ("月薪喵", "0xc73e1b136c576d1429cb84522a8c35c81d9d7777"),
    ("TKM", "0x86a5a545a5d9f7ee14afecb7e62b7ae7bab27777"),
    ("Racoonzilla", "0x12d5a0c58ef299bedd309ec4964ffa3145827777"),
    ("XchangetheWorld", "0xe9d476ce8ba9431a6c1ae39c00e84dab5c717777"),
    ("CSI", "0x2f31614f7a8bb702f7898d379b3c23db73b87777"),
    ("SpaceXcoin", "0xf225e70162837a811c77dc2bb413a5c06e97ffff"),
    ("币安城", "0x9ecfbb6c0ce91d5ac00e1f7378880523cb8d7777"),
)


def main() -> None:
    seeds = _load_seeds(ROOT / "bsc_universe.jsonl")
    rows = []
    with PublicDeBotClient(timeout_seconds=40, attempts=3) as client:
        for label, address in TARGETS:
            seed = seeds[address]
            bars = fetch_window_bars(
                client, seed, WINDOW_START, WINDOW_END_EXCLUSIVE, INTERVAL_SECONDS,
            )
            if not bars.coverage_complete or bars.total_supply is None:
                raise RuntimeError(f"incomplete market evidence for {address}")
            replay = replay_market_waves(bars.candles, bars.total_supply)
            rows.append({
                "schema": "debot4.bsc_week_wave_replay.v1",
                "label": label,
                "address": address,
                "created_at": seed.created_at,
                "window_start": WINDOW_START,
                "window_end_exclusive": WINDOW_END_EXCLUSIVE,
                "interval_seconds": INTERVAL_SECONDS,
                "candle_count": len(bars.candles),
                "coverage_complete": bars.coverage_complete,
                "total_supply_proxy": bars.total_supply,
                "ath": {
                    "at": replay.ath_at,
                    "high_price_usd": replay.ath_high_price_usd,
                    "fdv_usd": replay.ath_fdv_usd,
                },
                "completed_swings": tuple(asdict(item) for item in replay.completed_swings),
                "effective_wave_count": len(replay.effective_waves),
                "filtered_swing_count": replay.filtered_swing_count,
                "receipts": bars.receipts,
            })
            print(
                f"{label}: candles={len(bars.candles)} "
                f"waves={len(replay.effective_waves)} filtered={replay.filtered_swing_count}"
            )

    write_jsonl(ROOT / "bsc_week_wave_replays.jsonl", rows)
    counts = {row["label"]: row["effective_wave_count"] for row in rows}
    write_json(ROOT / "bsc_week_wave_replay_summary.json", {
        "schema": "debot4.bsc_week_wave_replay_summary.v1",
        "window_start": WINDOW_START,
        "window_end_exclusive": WINDOW_END_EXCLUSIVE,
        "interval_seconds": INTERVAL_SECONDS,
        "first_traded_candle_trough_field": "open",
        "later_trough_and_peak_field": "close",
        "minimum_multiple": MIN_WAVE_MULTIPLE,
        "reset_close_fraction": WAVE_RESET_FRACTION,
        "minimum_effective_peak_fdv_usd": MIN_WAVE_PEAK_FDV_USD,
        "ath_field": "5m_high",
        "supply_semantics": "current total-supply proxy returned by DeBot market API",
        "target_count": len(rows),
        "coverage_complete_count": sum(row["coverage_complete"] for row in rows),
        "effective_wave_total": sum(counts.values()),
        "effective_wave_counts": counts,
        "warning": (
            "A completed price wave is descriptive market evidence; it does not prove "
            "a narrative, account, wallet, manipulation, or profit cause."
        ),
    })


def _load_seeds(path: Path) -> dict[str, TokenSeed]:
    wanted = {address for _, address in TARGETS}
    seeds: dict[str, TokenSeed] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        address = str(row.get("address", "")).casefold()
        if address not in wanted:
            continue
        seeds[address] = TokenSeed(
            chain=str(row["chain"]),
            address=address,
            name=str(row["name"]),
            symbol=str(row["symbol"]),
            launchpad=str(row["launchpad"]),
            created_at=int(row["created_at"]),
            creator_address=row.get("creator_address"),
            rank_supply=(
                Decimal(str(row["rank_supply"]))
                if row.get("rank_supply") is not None else None
            ),
            current_kols=int(row["current_kols"]),
            max_kols=int(row["max_kols"]),
            social_urls=tuple(str(item) for item in row.get("social_urls", ())),
            discovered_sources=tuple(
                str(item) for item in row.get("discovered_sources", ())
            ),
        )
    missing = wanted - seeds.keys()
    if missing:
        raise RuntimeError(f"target seeds missing from universe: {len(missing)}")
    return seeds


if __name__ == "__main__":
    main()
