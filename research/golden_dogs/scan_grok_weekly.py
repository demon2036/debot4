#!/usr/bin/env python3
"""Restart-safe Grok lead discovery; model output never qualifies a token."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
from pathlib import Path
import json

from debot4.v6.golden_dogs.serialization import json_value
from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    successful_prompt_digests,
)
from debot4.v6.golden_dogs.weekly_scan import (
    consecutive_windows,
    prompt_sha256,
    sweep_prompts,
)
from debot4.v6.grok import Grok2ApiClient


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
START = datetime(2025, 8, 12, tzinfo=UTC)
END = datetime(2026, 8, 12, tzinfo=UTC)
INSTRUCTIONS = """
You are a historical crypto research locator. Search exhaustively but never claim
completeness. Return JSON with key candidates. Each candidate must include exact_ca,
name, symbol, launch_or_first_trade_at, claimed_peak_mc_or_fdv_usd, peak_at,
debot_or_gmgn_kol_buy, kol_alias_or_handle, wallet, buy_tx, buy_at, earliest_x_url,
other_direct_urls, and caveats. Use null for unknown. Distinguish a provider buy from
an X mention or token transfer. Flag shared funding, holder concentration, wash trading,
and post-pump KOL buys. Grok output is a lead, not verification.
""".strip()


def main() -> None:
    args = _args()
    windows = consecutive_windows(START, END)
    selected = windows[args.from_week:args.from_week + args.weeks]
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        done = _completed(journal)
        tasks = _tasks(selected, args.from_week, done)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {
                pool.submit(_scan, client, *task): task[2]
                for task in tasks
            }
            for future in as_completed(pending):
                row = future.result()
                _append(journal, row)
                print(f"{row['key']} {row['status']}", flush=True)


def _tasks(selected: tuple, offset: int, done: dict[str, str]) -> list[tuple]:
    tasks = []
    for index, window in enumerate(selected, start=offset):
        for sweep, prompt in enumerate(sweep_prompts(window), start=1):
            key = f"{window.key}:{sweep}"
            if not prompt_is_complete(done, key, prompt_sha256(prompt)):
                tasks.append((index, window, key, sweep, prompt))
    return tasks


def _scan(client: Grok2ApiClient, index: int, window, key: str,
          sweep: int, prompt: str) -> dict[str, object]:
    row: dict[str, object] = {
        "schema": "debot4.grok_weekly_lead.v1",
        "key": key,
        "week_index": index,
        "window_start": window.start,
        "window_end_exclusive": window.end_exclusive,
        "sweep": sweep,
        "prompt_sha256": prompt_sha256(prompt),
        "started_at": datetime.now(UTC),
        "grok_is_evidence": False,
    }
    try:
        answer = client.search_discovery(prompt, instructions=INSTRUCTIONS)
        row.update({
            "status": "success",
            "completed_at": datetime.now(UTC),
            "response_id": answer.response_id,
            "model": answer.model,
            "answer": answer.text,
            "sources": [asdict(item) for item in answer.sources],
            "citations": [asdict(item) for item in answer.citations],
            "candidate_urls": answer.candidate_urls,
            "usage": answer.usage,
        })
    except Exception as exc:
        row.update({
            "status": "error",
            "completed_at": datetime.now(UTC),
            "error_type": type(exc).__name__,
        })
    return row


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-week", type=int, default=0)
    parser.add_argument("--weeks", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    parser.add_argument("--output", default="grok_weekly_leads.jsonl")
    args = parser.parse_args()
    if (args.from_week < 0 or args.weeks <= 0 or not 0 < args.timeout <= 300
            or not 1 <= args.workers <= 8):
        parser.error("invalid bounded scan arguments")
    return args


def _completed(handle) -> dict[str, str]:
    handle.seek(0)
    return successful_prompt_digests(handle)


def _append(handle, row: dict[str, object]) -> None:
    line = json.dumps(
        json_value(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    )
    handle.seek(0, 2)
    handle.write(line + "\n")
    handle.flush()


if __name__ == "__main__":
    main()
