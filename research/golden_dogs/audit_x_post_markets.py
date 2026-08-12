#!/usr/bin/env python3
"""Fetch minute bars and measure the remaining move after verified X posts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time

from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_post_market import assess_x_post_market


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    candidates = tuple(row for row in _jsonl("x_kol_buy_intersections.jsonl")
                       if row["x_post_timing"] == "pre_peak"
                       and row["kol_buy_audit"]["rpc_verified_clean_buy_count"] > 0)
    roles = {str(row["stable_user_id"]): row for row in
             _jsonl("x_account_candidate_queue.jsonl")}
    rows: list[dict] = []
    errors: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = {pool.submit(_audit, item, roles): item for item in candidates}
        for job in as_completed(jobs):
            item = jobs[job]
            try:
                rows.append(job.result())
            except Exception as exc:
                errors.append({
                    "address": item["address"], "status_url": item["x"]["status_url"],
                    "error_type": type(exc).__name__,
                })
    rows.sort(key=lambda row: (row["x"]["published_at"], row["address"]))
    errors.sort(key=lambda row: (row["status_url"], row["address"]))
    write_jsonl(ROOT / "x_post_market_trajectories.jsonl", rows)
    write_jsonl(ROOT / "x_post_market_errors.jsonl", errors)
    write_json(ROOT / "x_post_market_summary.json", _summary(rows, errors, candidates))


def _audit(item: dict, roles: dict[str, dict]) -> dict:
    post_at = int(datetime.fromisoformat(
        item["x"]["published_at"].replace("Z", "+00:00"),
    ).timestamp())
    trace = None
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with PublicDeBotClient(attempts=3) as client:
                trace = client.fetch_market(
                    "bsc", item["address"], interval_seconds=60,
                    limit=30, end=post_at + 600,
                )
            break
        except Exception as exc:
            last_error = exc
            time.sleep(0.25 * (2**attempt))
    if trace is None:
        assert last_error is not None
        raise last_error
    market = item["market"]
    trajectory = assess_x_post_market(
        trace.candles,
        total_supply=Decimal(str(market["total_supply"])),
        post_at=post_at, peak_at=int(market["peak_at"]),
        peak_fdv_usd=Decimal(str(market["approx_peak_fdv_usd"])),
    )
    account = roles.get(str(item["x"]["stable_user_id"]), {})
    return {
        "schema": "debot4.x_post_market_trajectory.v1",
        "address": item["address"], "token": item["token"],
        "x": item["x"], "trajectory": asdict(trajectory),
        "account_role": account.get("reviewed_role"),
        "account_monitor_candidate": account.get("monitor_candidate") is True,
        "kol_buy_audit": item["kol_buy_audit"],
        "market_receipt": asdict(trace.receipt),
        "warning": (
            "The post-time FDV uses the last one-minute candle open known at the post. "
            "It is an OHLC/current-supply proxy, not proof that the post caused the move."
        ),
    }


def _summary(rows: list[dict], errors: list[dict], candidates: tuple[dict, ...]) -> dict:
    complete_accounts = {row["x"]["stable_user_id"] for row in rows}
    return {
        "schema": "debot4.x_post_market_summary.v1",
        "generated_at": datetime.now(UTC), "candidate_pairs": len(candidates),
        "complete_pairs": len(rows), "error_pairs": len(errors),
        "complete_accounts": len(complete_accounts),
        "unique_tokens": len({row["address"] for row in rows}),
        "at_least_2x_after_post": sum(
            Decimal(str(row["trajectory"]["post_to_peak_multiple"])) >= 2 for row in rows
        ),
        "at_least_5x_after_post": sum(
            Decimal(str(row["trajectory"]["post_to_peak_multiple"])) >= 5 for row in rows
        ),
        "warning": "Market trajectory does not establish post authorship role or causation.",
    }


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


if __name__ == "__main__":
    main()
