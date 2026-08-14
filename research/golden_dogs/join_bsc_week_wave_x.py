#!/usr/bin/env python3
"""Time-join strict Exact-CA X posts to all 32 effective BSC waves."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.market_waves import wave_phase_bounds


ROOT = Path(__file__).resolve().parent
REPLAYS = ROOT / "bsc_week_wave_replays.jsonl"
EVIDENCE = ROOT / "bsc_week_x_exact_evidence.jsonl"
def main() -> None:
    posts = _posts_by_address()
    rows: list[dict[str, object]] = []
    for replay in _jsonl(REPLAYS):
        address = str(replay["address"]).casefold()
        effective = [wave for wave in replay["completed_swings"] if wave["effective"]]
        for wave_number, wave in enumerate(effective, 1):
            bounds = wave_phase_bounds(
                window_start=int(replay["window_start"]),
                window_end_exclusive=int(replay["window_end_exclusive"]),
                trough_at=int(wave["trough_at"]),
                peak_at=int(wave["peak_at"]),
                reset_at=int(wave["reset_at"]),
            )
            target_posts = posts.get(address, ())
            row = {
                "schema": "debot4.bsc_week_wave_x_join.v1",
                "label": replay["label"], "address": address,
                "wave_number": wave_number, "wave": wave,
                "timing_semantics": {
                    "historical_baseline": "fixed-window posts before the 30m pre-trough lane",
                    "pre_trough": "30m immediately before trough-candle start",
                    "ascent": "trough-candle start through peak-candle end",
                    "decay": "after peak-candle end through reset-candle end",
                    "later": "after reset-candle end within fixed week",
                },
                "historical_baseline": _select(
                    target_posts, bounds.historical_start,
                    bounds.pre_trough_start, bounds.trough_start,
                ),
                "pre_trough": _select(
                    target_posts, bounds.pre_trough_start,
                    bounds.trough_start, bounds.trough_start,
                ),
                "ascent": _select(
                    target_posts, bounds.trough_start,
                    bounds.peak_end_exclusive, bounds.trough_start,
                ),
                "decay": _select(
                    target_posts, bounds.peak_end_exclusive,
                    bounds.reset_end_exclusive, bounds.trough_start,
                ),
                "later": _select(
                    target_posts, bounds.reset_end_exclusive,
                    bounds.window_end_exclusive, bounds.trough_start,
                ),
            }
            rows.append(row)
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 effective wave joins, got {len(rows)}")
    write_jsonl(ROOT / "bsc_week_wave_x_joins.jsonl", rows)
    write_json(ROOT / "bsc_week_wave_x_join_summary.json", {
        "schema": "debot4.bsc_week_wave_x_join_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "waves_with_pre_trough_exact_posts": sum(bool(row["pre_trough"]) for row in rows),
        "waves_with_ascent_exact_posts": sum(bool(row["ascent"]) for row in rows),
        "waves_with_decay_exact_posts": sum(bool(row["decay"]) for row in rows),
        "source_sha256": {
            REPLAYS.name: sha256(REPLAYS.read_bytes()).hexdigest(),
            EVIDENCE.name: sha256(EVIDENCE.read_bytes()).hexdigest(),
        },
        "warning": (
            "Timing proximity is descriptive, not causal proof. A historical-baseline "
            "post may explain the standing narrative but cannot be a direct wave trigger."
        ),
    })
    print(f"joined strict X evidence to {len(rows)} waves")


def _posts_by_address() -> dict[str, tuple[dict[str, object], ...]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in _jsonl(EVIDENCE):
        grouped.setdefault(str(row["address"]).casefold(), []).append(row)
    return {
        address: tuple(sorted(rows, key=lambda row: str(row["published_at"])))
        for address, rows in grouped.items()
    }


def _select(
    rows: tuple[dict[str, object], ...], start: int, end: int, trough: int,
) -> list[dict[str, object]]:
    selected = []
    for row in rows:
        timestamp = int(_time(str(row["published_at"])).timestamp())
        if start <= timestamp < end:
            selected.append({
                "published_at": row["published_at"],
                "seconds_from_trough": timestamp - trough,
                "author_handle": row["author_handle"], "status_url": row["status_url"],
                "text": row["text"], "text_sha256": row["text_sha256"],
                "status_payload_sha256": row["status_payload_sha256"],
            })
    return selected


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


if __name__ == "__main__":
    main()
