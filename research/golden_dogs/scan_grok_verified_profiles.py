#!/usr/bin/env python3
"""Restart-safe exact-CA and account-link sweep for every verified Chinese X profile."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    successful_prompt_digests,
)
from debot4.v6.golden_dogs.serialization import json_value
from debot4.v6.grok import Grok2ApiClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
INSTRUCTIONS = """
You locate historical public X evidence. Return compact JSON with keys findings,
account_links, and caveats. Each finding needs stable_user_id, handle, status_url,
post_at, exact_ca, literal_text, and semantic_role. Each account link needs a direct
profile or status URL and the literal relationship claim. Never infer a CA from a ticker,
never substitute another author, never infer ownership or a hidden wallet, and never
invent. Model output is a lead only; direct X resources will be fetched independently.
""".strip()


def main() -> None:
    args = _args()
    excluded_ids = _verified_ids(tuple(ROOT / name for name in args.exclude_input))
    tasks = tuple(
        task for task in _tasks(ROOT / args.input) if task[3] not in excluded_ids
    )
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        journal.seek(0)
        done = successful_prompt_digests(journal)
        selected = tuple(task for task in tasks if not prompt_is_complete(
            done, task[0], task[2],
        ))
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(_scan, client, task): task[0] for task in selected}
            for future in as_completed(pending):
                row = future.result()
                _append(journal, row)
                print(f"{row['key']} {row['status']}", flush=True)


def _tasks(path: Path) -> tuple[tuple[str, str, str, str], ...]:
    rows = (json.loads(line) for line in path.read_text(encoding="utf-8").splitlines())
    tasks = []
    for row in rows:
        if row.get("status") != "verified":
            continue
        stable_id = str(row["profile_user_id"])
        handle = str(row["profile_handle"])
        prompt = f"""
Carpet-search posts authored by @{handle} (stable X user ID {stable_id}, display name
{row.get('profile_display_name')!r}) during UTC [2025-08-12, 2026-08-13).

Find every authored post containing a literal 0x{{40 hex}} BSC/BNB meme-token contract.
Search from:{handle}, replies, quote posts, Chinese names/aliases, and exact-address
follow-ups. Preserve direct status URL, time, literal CA, and enough literal text to
classify own position/call, market thesis, research, reply, relay, project, scanner,
warning, or recap. Also find direct self-disclosures of old, main, backup, second, or
alternate X accounts. A wallet may have bought days before a post, so do not impose a
same-day or repeated-hit rule; however wallets are secondary and must not be inferred.
Return empty arrays when nothing direct is found.
""".strip()
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        tasks.append((f"verified-profile:{stable_id}", prompt, digest, stable_id))
    return tuple(sorted(tasks))


def _verified_ids(paths: tuple[Path, ...]) -> frozenset[str]:
    output = set()
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("status") == "verified" and row.get("profile_user_id"):
                output.add(str(row["profile_user_id"]))
    return frozenset(output)


def _scan(client: Grok2ApiClient, task: tuple[str, str, str, str]) -> dict[str, object]:
    key, prompt, digest, stable_id = task
    row: dict[str, object] = {
        "schema": "debot4.grok_verified_profile_lead.v1",
        "key": key, "stable_user_id": stable_id,
        "prompt_sha256": digest, "started_at": datetime.now(UTC),
        "grok_is_evidence": False,
    }
    try:
        answer = client.search_x(prompt, instructions=INSTRUCTIONS)
        row.update({
            "status": "success", "completed_at": datetime.now(UTC),
            "response_id": answer.response_id, "model": answer.model,
            "answer": answer.text,
            "sources": [asdict(item) for item in answer.sources],
            "citations": [asdict(item) for item in answer.citations],
            "candidate_urls": answer.candidate_urls, "usage": answer.usage,
        })
    except Exception as exc:
        row.update({
            "status": "error", "completed_at": datetime.now(UTC),
            "error_type": type(exc).__name__,
        })
    return row


def _append(handle, row: dict[str, object]) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(
        json_value(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n")
    handle.flush()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="grok_chinese_profile_verified.jsonl")
    parser.add_argument("--exclude-input", action="append", default=[])
    parser.add_argument("--output", default="grok_chinese_profile_deep_leads.jsonl")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=170)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.timeout <= 300:
        parser.error("invalid bounded scan arguments")
    return args


if __name__ == "__main__":
    main()
