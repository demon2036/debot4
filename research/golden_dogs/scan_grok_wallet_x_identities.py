#!/usr/bin/env python3
"""Restart-safe X search around independently bound GMGN/RPC wallet identities."""

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
from debot4.v6.grok import Grok2ApiClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
INSTRUCTIONS = """
You investigate X identities associated with provider-bound BSC wallets. Search native X
exhaustively and return compact JSON with keys accounts and caveats. For each stable ID,
return stable_user_id, current_handle, aliases_or_old_handles, direct_profile_url,
likely_role, role_reason, authored_exact_ca_status_urls, linked_or_secondary_accounts,
direct_link_evidence_urls, public_wallet_claims, wallet_attribution_urls, and confidence.
Linked/secondary accounts require a direct public source; never infer them from names,
writing style, timing, or wallet behavior. Do not claim a hidden wallet. A wallet can buy
days before one post and need not repeat. Distinguish caller, scanner/bot, project,
catalyst, repost, and post-pump recap. Provider wallet binding is supplied evidence, but
full activity denominators and smart-wallet quality remain unknown. Never manufacture a
URL. Every direct X URL will be independently fetched; model output is only a lead.
""".strip()


def main() -> None:
    args = _args()
    tasks = _tasks(
        args.batch_size,
        args.min_pre_peak_tokens,
        frozenset(args.stable_user_id),
    )
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


def _tasks(
    batch_size: int,
    minimum: int,
    focus_ids: frozenset[str] = frozenset(),
) -> tuple[tuple, ...]:
    high_frequency = _high_frequency_wallets()
    by_identity: dict[str, dict[str, object]] = {}
    for row in _jsonl("bsc_audit_wallet_x_verified.jsonl"):
        binding = row.get("x_binding") or {}
        wallet = str(row["wallet"]).casefold()
        if (binding.get("verdict") != "PASS" or row.get("status") != "complete"
                or int(row.get("pre_peak_token_count", 0)) < minimum):
            continue
        identity = str(binding["stable_user_id"])
        item = by_identity.setdefault(identity, {
            "stable_user_id": identity, "handle": binding["canonical_handle"],
            "display_name": (row.get("x_profile") or {}).get("display_name"),
            "description": (row.get("x_profile") or {}).get("description"),
            "wallet_evidence": [],
        })
        item["wallet_evidence"].append({
            "wallet": wallet, "provider_name": row.get("provider_name"),
            "eligible_token_count": row.get("eligible_token_count"),
            "pre_peak_token_count": row.get("pre_peak_token_count"),
            "buy_transaction_count": row.get("buy_transaction_count"),
            "provider_high_frequency_7d": wallet in high_frequency,
            "sample_buys": [{
                "exact_ca": buy["token"], "bought_at": buy["bought_at"],
                "transaction_hash": buy["transaction_hash"],
                "before_peak": buy["before_market_peak"],
            } for buy in row.get("sample_rpc_verified_buys", [])[:3]],
        })
    selected = sorted(by_identity.values(), key=lambda row: (
        -max(int(item["pre_peak_token_count"]) for item in row["wallet_evidence"]),
        str(row["handle"]),
    ))
    if focus_ids:
        selected = [
            row for row in selected if str(row["stable_user_id"]) in focus_ids
        ]
        missing = focus_ids - {
            str(row["stable_user_id"]) for row in selected
        }
        if missing:
            raise ValueError(
                "requested stable user IDs are not eligible: " + ",".join(sorted(missing))
            )
    effective_batch_size = 1 if focus_ids else batch_size
    tasks = []
    for offset in range(0, len(selected), effective_batch_size):
        batch = selected[offset:offset + effective_batch_size]
        prompt = (
            "Investigate these provider-bound BSC wallet/X identities over 2025-08-12 "
            "through 2026-08-12. Prioritize the real X person/account, aliases, direct "
            "authored exact-CA posts, and directly evidenced secondary accounts. The "
            "provider_high_frequency_7d flag is only a smart-wallet risk and must not "
            "erase an X/KOL identity. Preserve direct URLs.\n" +
            json.dumps(batch, ensure_ascii=False, separators=(",", ":"))
        )
        digest = sha256(prompt.encode("utf-8")).hexdigest()
        identity_ids = tuple(str(row["stable_user_id"]) for row in batch)
        key = (
            f"wallet-x-focused-{identity_ids[0]}" if focus_ids
            else f"wallet-x-identity-{offset // batch_size:03d}"
        )
        tasks.append((key, prompt, digest, identity_ids))
    return tuple(tasks)


def _high_frequency_wallets() -> frozenset[str]:
    return frozenset(
        str(row["wallet"]).casefold()
        for row in _jsonl("gmgn_bsc_kol_rank_x_verified.jsonl")
        if (row.get("frequency_screen") or {}).get("verdict") == "REJECT"
    )


def _scan(client: Grok2ApiClient, task: tuple) -> dict[str, object]:
    key, prompt, digest, identities = task
    row: dict[str, object] = {
        "schema": "debot4.grok_wallet_x_identity_lead.v1", "key": key,
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


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="grok_wallet_x_identity_leads.jsonl")
    parser.add_argument("--batch-size", type=int, default=3)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=170)
    parser.add_argument("--min-pre-peak-tokens", type=int, default=1)
    parser.add_argument("--stable-user-id", action="append", default=[])
    args = parser.parse_args()
    if not 1 <= args.batch_size <= 5 or not 1 <= args.workers <= 8:
        parser.error("invalid bounded scan arguments")
    if not 0 < args.timeout <= 300 or args.min_pre_peak_tokens < 1:
        parser.error("invalid timeout or minimum pre-peak token count")
    if any(not value.isdigit() for value in args.stable_user_id):
        parser.error("stable user IDs must contain only digits")
    args.stable_user_id = tuple(dict.fromkeys(args.stable_user_id))
    return args


if __name__ == "__main__":
    main()
