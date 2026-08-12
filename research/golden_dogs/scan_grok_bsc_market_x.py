#!/usr/bin/env python3
"""Restart-safe Grok search over every independently measured BSC market CA."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import json_value
from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    successful_prompt_digests,
)
from debot4.v6.golden_dogs.x_exact_scan import XSearchSeed, exact_ca_x_tasks
from debot4.v6.grok import Grok2ApiClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
INSTRUCTIONS = """
You are a historical evidence locator. Search X and public web sources exhaustively but
return compact JSON with keys findings, no_hit_exact_cas, and caveats. Every finding
must contain exact_ca, alias, handle, display_name, role, direct_status_urls, post_at,
wallet, buy_tx, buy_at, provider, attribution_urls, and claim_type. Use null or [] for
unknown. Never manufacture evidence. Your output is only a lead and will be fetched
again from independent public endpoints.
""".strip()


def main() -> None:
    args = _args()
    seeds = _seeds(ROOT / args.input)
    tasks = exact_ca_x_tasks(seeds, batch_size=args.batch_size)
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        completed = _completed(journal)
        selected = tuple(task for task in tasks if not prompt_is_complete(
            completed, task.key, task.prompt_sha256,
        ))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(_scan, client, task): task.key for task in selected}
            for future in as_completed(pending):
                row = future.result()
                _append(journal, row)
                print(f"{row['key']} {row['status']}", flush=True)


def _scan(client: Grok2ApiClient, task) -> dict[str, object]:
    row: dict[str, object] = {
        "schema": "debot4.grok_bsc_market_x_lead.v1",
        "key": task.key, "lane": task.lane,
        "addresses": task.addresses, "prompt_sha256": task.prompt_sha256,
        "started_at": datetime.now(UTC), "grok_is_evidence": False,
    }
    try:
        search = client.search_x if task.lane == "authored_posts" else client.search_discovery
        answer = search(task.prompt, instructions=INSTRUCTIONS)
        row.update({
            "status": "success", "completed_at": datetime.now(UTC),
            "response_id": answer.response_id, "model": answer.model,
            "answer": answer.text, "sources": [asdict(item) for item in answer.sources],
            "citations": [asdict(item) for item in answer.citations],
            "candidate_urls": answer.candidate_urls, "usage": answer.usage,
        })
    except Exception as exc:
        row.update({
            "status": "error", "completed_at": datetime.now(UTC),
            "error_type": type(exc).__name__,
        })
    return row


def _seeds(path: Path) -> tuple[XSearchSeed, ...]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    return tuple(XSearchSeed(
        address=str(row["address"]), name=str(row["name"]), symbol=str(row["symbol"]),
        created_at=int(row["created_at"]), peak_at=int(row["peak_at"]),
        window_start=int(row["window_start"]),
        window_end_exclusive=int(row["window_end_exclusive"]),
        peak_fdv_usd=str(row["approx_peak_fdv_usd"]), max_kols=int(row["max_kols"]),
    ) for row in rows if row.get("meets_peak_threshold") is True)


def _completed(handle) -> dict[str, str]:
    handle.seek(0)
    return successful_prompt_digests(handle)


def _append(handle, row: dict[str, object]) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(
        json_value(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n")
    handle.flush()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="bsc_market_candidates.jsonl")
    parser.add_argument("--output", default="grok_bsc_market_x_leads.jsonl")
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 10 or not 1 <= args.workers <= 8:
        parser.error("invalid bounded scan arguments")
    if not 0 < args.timeout <= 300:
        parser.error("timeout must be between zero and 300 seconds")
    return args


if __name__ == "__main__":
    main()
