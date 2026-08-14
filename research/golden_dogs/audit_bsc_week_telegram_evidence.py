#!/usr/bin/env python3
"""Directly verify Telegram leads used in the fixed BSC-week wave audit."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.telegram import TelegramPublicClient, TelegramUnavailable
from debot4.v6.telegram.http import TelegramHttpError


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "bsc_week_telegram_candidates.json"
OUTPUT = ROOT / "bsc_week_telegram_evidence.jsonl"
WINDOW_START = datetime(2026, 8, 6, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 13, tzinfo=timezone.utc)


def main() -> None:
    candidates = json.loads(CONFIG.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(_audit, item): item for item in candidates}
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            print(f"{row['status']}: {row['canonical_url']}", flush=True)
    rows.sort(key=lambda row: (
        str(row.get("created_at") or "9999"), str(row["canonical_url"]),
    ))
    write_jsonl(OUTPUT, rows)
    direct = [row for row in rows if row["status"] == "direct_verified"]
    write_json(ROOT / "bsc_week_telegram_evidence_summary.json", {
        "schema": "debot4.bsc_week_telegram_evidence_summary.v1",
        "window": {"start": WINDOW_START, "end_exclusive": WINDOW_END},
        "candidate_count": len(candidates),
        "direct_verified_count": len(direct),
        "unavailable_count": len(rows) - len(direct),
        "independent_forward_signal_count": sum(
            bool(row["independent_forward_signal"]) for row in direct
        ),
        "source_sha256": {CONFIG.name: sha256(CONFIG.read_bytes()).hexdigest()},
        "warning": (
            "Semantic labels are manual content review. Direct availability proves the "
            "message and timestamp, not authorship independence or price causation."
        ),
    })


def _audit(item: dict[str, object]) -> dict[str, object]:
    channel = str(item["channel"])
    message_id = int(item["message_id"])
    canonical = f"https://t.me/{channel.casefold()}/{message_id}"
    base = {
        "schema": "debot4.bsc_week_telegram_evidence.v1",
        "label": item["label"],
        "address": str(item["address"]).casefold(),
        "canonical_url": canonical,
        "semantic": item["semantic"],
        "independent_forward_signal": item["independent_forward_signal"],
        "lead_basis": item["lead_basis"],
    }
    try:
        observation = TelegramPublicClient().get_observation(channel, message_id)
    except (TelegramUnavailable, TelegramHttpError) as exc:
        return {
            **base,
            "status": "unavailable_at_fetch",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "direct_content_verified": False,
        }
    post = observation.post
    if not WINDOW_START <= post.created_at < WINDOW_END:
        raise RuntimeError(f"Telegram post outside fixed window: {post.canonical_url}")
    address = str(base["address"])
    searchable = "\n".join((post.text, *post.urls)).casefold()
    return {
        **base,
        "status": "direct_verified",
        "canonical_url": post.canonical_url,
        "channel": post.channel,
        "message_id": post.message_id,
        "created_at": post.created_at,
        "fetched_at": post.fetched_at,
        "text": post.text,
        "text_sha256": sha256(post.text.encode()).hexdigest(),
        "urls": post.urls,
        "parsed_bsc_contracts": post.bsc_contracts,
        "exact_ca_literal_or_url": address in searchable,
        "has_media": post.has_media,
        "raw_payload_bytes": len(observation.raw_payload),
        "raw_payload_sha256": sha256(observation.raw_payload).hexdigest(),
        "response_identity": observation.response_identity,
        "direct_content_verified": True,
    }


if __name__ == "__main__":
    main()
