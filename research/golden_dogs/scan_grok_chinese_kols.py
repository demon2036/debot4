#!/usr/bin/env python3
"""Restart-safe Grok lead scan for Chinese BSC KOL identities and evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import date, datetime, timezone
import fcntl
import json
from pathlib import Path

from debot4.v6.golden_dogs.kol_search import KolSearchTask, chinese_kol_search_tasks
from debot4.v6.golden_dogs.serialization import json_value
from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    successful_prompt_digests,
)
from debot4.v6.grok import Grok2ApiClient


UTC = timezone.utc
ROOT = Path(__file__).resolve().parent
START = date(2025, 8, 12)
END_EXCLUSIVE = date(2026, 8, 13)
INSTRUCTIONS = """
You are a historical source locator. Search X and the public web carefully. Return compact
JSON with keys findings and caveats. Each finding should include alias, handle, role,
profile_url, direct_status_urls, exact_bsc_ca, provider, wallet, buy_tx, observed_at,
attribution_url, and claim_type. Use null or [] for unknown. Never manufacture evidence,
never equate a token CA with a wallet, and never claim completeness. Model output is a
lead only and will be independently fetched and verified.
""".strip()


def main() -> None:
    args = _args()
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    tasks = chinese_kol_search_tasks(START, END_EXCLUSIVE)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        done = _completed(journal)
        selected = tuple(item for item in tasks if not prompt_is_complete(
            done, item.key, item.prompt_sha256,
        ))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(_scan, client, item): item.key for item in selected}
            for future in as_completed(futures):
                row = future.result()
                _append(journal, row)
                print(f"{row['key']} {row['status']}", flush=True)


def _scan(client: Grok2ApiClient, task: KolSearchTask) -> dict[str, object]:
    row: dict[str, object] = {
        "schema": "debot4.grok_chinese_kol_lead.v1",
        "key": task.key,
        "lane": task.lane,
        "prompt_sha256": task.prompt_sha256,
        "started_at": datetime.now(UTC),
        "grok_is_evidence": False,
    }
    try:
        search = client.search_x if task.lane == "x" else client.search_discovery
        answer = search(task.prompt, instructions=INSTRUCTIONS)
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


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    parser.add_argument("--output", default="grok_chinese_kol_leads.jsonl")
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.timeout <= 300:
        parser.error("invalid bounded scan arguments")
    return args


if __name__ == "__main__":
    main()
