#!/usr/bin/env python3
"""Restart-safe Grok search for aliases, role, and earlier calls of X candidates."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import fcntl
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import json_value
from debot4.v6.golden_dogs.grok_journal import (
    prompt_is_complete,
    successful_prompt_digests,
)
from debot4.v6.golden_dogs.x_account_queue import is_excluded_x_account_role
from debot4.v6.grok import Grok2ApiClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
INSTRUCTIONS = """
You are an X identity and source investigator. Search native X exhaustively, but return
compact JSON with keys accounts and caveats. For every supplied stable user ID, return:
stable_user_id, current_handle, aliases_or_old_handles, likely_role, role_reason,
direct_profile_url, direct_status_urls, earlier_exact_ca_status_urls, linked_accounts,
public_wallet_claims, wallet_attribution_urls, and confidence. Distinguish a human caller,
scanner/bot, project account, catalyst, repost, and post-pump recap. A wallet is optional;
never infer it from a similar name. An early wallet may buy days before a post and need
not repeat across tokens. Never manufacture evidence. Model output is only a lead; every
direct status/profile will be independently fetched by another process.
""".strip()


def main() -> None:
    args = _args()
    tasks = _tasks(ROOT / args.input, args.batch_size, args.all_accounts)
    output = ROOT / args.output
    client = Grok2ApiClient.from_env(timeout_seconds=args.timeout, attempts=1)
    with output.open("a+", encoding="utf-8") as journal:
        fcntl.flock(journal, fcntl.LOCK_EX)
        completed = _completed(journal)
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


def _tasks(path: Path, batch_size: int, all_accounts: bool) -> tuple[tuple, ...]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    selected = [row for row in rows if row.get("has_pre_peak_exact_ca_post") is True]
    if not all_accounts:
        selected = [row for row in selected if not is_excluded_x_account_role(
            row.get("reviewed_role"),
        )]
    selected.sort(key=lambda row: (
        -int(row["pre_peak_post_token_count"]), str(row["handle"]),
    ))
    tasks = []
    for offset in range(0, len(selected), batch_size):
        batch = selected[offset:offset + batch_size]
        payload = [{
            "stable_user_id": row["stable_user_id"], "handle": row["handle"],
            "display_name": row["display_name"],
            "description": (row.get("profile") or {}).get("description"),
            "known_role": row.get("reviewed_role"),
            "sample_posts": [{
                "status_url": post["status_url"], "exact_ca": post["address"],
                "published_at": post["published_at"], "text": post["text"][:800],
            } for post in row["sample_pre_peak_posts"][:2]],
        } for row in batch]
        prompt = (
            "Investigate these BSC exact-CA X identities over 2025-08-12 through "
            "2026-08-12. Find aliases/old handles, classify role, and locate any earlier "
            "authored exact-CA posts or source posts preceding the supplied examples. "
            "Preserve stable IDs and direct URLs.\n" +
            json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        )
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        tasks.append((f"x-account-identity-{offset // batch_size:03d}", prompt, digest,
                      tuple(str(row["stable_user_id"]) for row in batch)))
    return tuple(tasks)


def _scan(client: Grok2ApiClient, task: tuple) -> dict[str, object]:
    key, prompt, digest, identities = task
    row: dict[str, object] = {
        "schema": "debot4.grok_x_account_identity_lead.v1", "key": key,
        "stable_user_ids": identities, "prompt_sha256": digest,
        "started_at": datetime.now(UTC), "grok_is_evidence": False,
    }
    try:
        answer = client.search_x(prompt, instructions=INSTRUCTIONS)
        row.update({
            "status": "success", "completed_at": datetime.now(UTC),
            "response_id": answer.response_id, "model": answer.model,
            "answer": answer.text, "sources": [asdict(item) for item in answer.sources],
            "citations": [asdict(item) for item in answer.citations],
            "candidate_urls": answer.candidate_urls, "usage": answer.usage,
        })
    except Exception as exc:
        row.update({"status": "error", "completed_at": datetime.now(UTC),
                    "error_type": type(exc).__name__})
    return row


def _completed(handle) -> dict[str, str]:
    handle.seek(0)
    return successful_prompt_digests(handle)


def _append(handle, row: dict[str, object]) -> None:
    handle.seek(0, 2)
    handle.write(json.dumps(json_value(row), ensure_ascii=False, sort_keys=True,
                            separators=(",", ":")) + "\n")
    handle.flush()


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="x_account_candidate_queue.jsonl")
    parser.add_argument("--output", default="grok_x_account_identity_leads.jsonl")
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    parser.add_argument("--all-accounts", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5 or not 1 <= args.workers <= 8:
        parser.error("invalid bounded scan arguments")
    if not 0 < args.timeout <= 300:
        parser.error("timeout must be between zero and 300 seconds")
    return args


if __name__ == "__main__":
    main()
