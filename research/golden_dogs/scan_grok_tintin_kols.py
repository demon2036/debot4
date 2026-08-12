#!/usr/bin/env python3
"""Restart-safe exact-CA X sweep for verified Tintin-directory profiles."""

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
You are a historical X source locator. Return compact JSON with keys findings and
caveats. A finding must include stable_user_id, handle, status_url, post_at, exact_ca,
literal_text, semantic_role, and earliest_source_url. Search only public X. Never infer a
CA from a ticker, never substitute another author's post, and never invent a result.
The model output is a lead only; every status and profile will be fetched independently.
""".strip()


def main() -> None:
    args = _args()
    tasks = _tasks(ROOT / args.input)
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        journal.seek(0)
        completed = successful_prompt_digests(journal)
        selected = tuple(
            task for task in tasks
            if not prompt_is_complete(completed, task[0], task[2])
        )
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            pending = {pool.submit(_scan, client, task): task[0] for task in selected}
            for future in as_completed(pending):
                row = future.result()
                _append(journal, row)
                print(f"{row['key']} {row['status']}", flush=True)


def _tasks(path: Path) -> tuple[tuple[str, str, str, str], ...]:
    rows = [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    tasks = []
    for row in rows:
        if row.get("status") != "verified":
            continue
        profile = row["profile"]
        handle = str(profile["handle"])
        stable_id = str(profile["user_id"])
        prompt = f"""
Carpet-search authored posts by @{handle} (stable X user ID {stable_id}, display name
{profile['display_name']!r}) during UTC [2025-08-12, 2026-08-13). Directory section:
{row.get('directory_section')!r}.

Find every post by this exact author containing a literal 0x{{40 hex}} BSC/BNB meme
token contract. Use from:{handle} searches, exact-address follow-up, Chinese aliases,
replies, and quote posts. Preserve direct status URL, exact post time and literal CA.
Classify own position/call, market thesis, research, reply mention, relay, project post,
scanner, warning, or recap. Locate an earlier source only when a direct URL exists.
Return an empty findings array if no exact authored post is found. Wallets are optional
and outside this task. Do not claim this account is a KOL merely because a directory
listed it.
""".strip()
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        tasks.append((f"tintin:{stable_id}", prompt, digest, stable_id))
    return tuple(sorted(tasks))


def _scan(client: Grok2ApiClient, task: tuple[str, str, str, str]) -> dict[str, object]:
    key, prompt, digest, stable_id = task
    row: dict[str, object] = {
        "schema": "debot4.grok_tintin_kol_lead.v1",
        "key": key,
        "stable_user_id": stable_id,
        "prompt_sha256": digest,
        "started_at": datetime.now(UTC),
        "grok_is_evidence": False,
    }
    try:
        answer = client.search_x(prompt, instructions=INSTRUCTIONS)
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


def _append(handle, row: dict[str, object]) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(
        json_value(row), ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ) + "\n")
    handle.flush()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="tintin_directory_profiles.jsonl")
    parser.add_argument("--output", default="grok_tintin_kol_leads.jsonl")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 0 < args.timeout <= 300:
        parser.error("invalid bounded scan arguments")
    return args


if __name__ == "__main__":
    main()
