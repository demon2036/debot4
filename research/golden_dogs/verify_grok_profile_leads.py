#!/usr/bin/env python3
"""Independently fetch stable X profiles found in Grok lead journals."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_profile_leads import XProfileLead, successful_profile_leads
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    args = _args()
    leads = _leads(tuple(ROOT / name for name in args.input))
    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(_verify, lead): lead.handle for lead in leads}
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            print(f"{row['claimed_handle']} {row['status']}", flush=True)
    rows.sort(key=lambda row: str(row["claimed_handle"]))
    write_jsonl(ROOT / args.output, rows)
    write_json(ROOT / args.summary, _summary(rows, len(leads)))


def _leads(paths: tuple[Path, ...]) -> tuple[XProfileLead, ...]:
    lines = (
        line for path in paths for line in path.read_text(encoding="utf-8").splitlines()
    )
    return successful_profile_leads(lines)


def _verify(lead: XProfileLead) -> dict[str, object]:
    base: dict[str, object] = {
        "schema": "debot4.grok_profile_verification.v1",
        "claimed_handle": lead.handle,
        "lead_candidate_urls": lead.candidate_urls,
        "lead_task_keys": lead.task_keys,
        "grok_is_evidence": False,
        "verified_at": datetime.now(UTC),
    }
    try:
        observed = XProfileClient().fetch_observation(lead.handle)
        profile = observed.profile
        return {
            **base, "status": "verified",
            "profile_user_id": profile.user_id,
            "profile_handle": profile.handle,
            "profile_display_name": profile.display_name,
            "profile_description": profile.description,
            "profile_fetched_at": profile.fetched_at,
            "profile_source_url": observed.source_url,
            "profile_response_bytes": observed.response_bytes,
            "profile_payload_sha256": observed.sha256,
            "profile_response_identity": observed.response_identity,
        }
    except Exception as exc:
        return {**base, "status": "profile_unavailable", "error_type": type(exc).__name__}


def _summary(rows: list[dict[str, object]], lead_count: int) -> dict[str, object]:
    verified = [row for row in rows if row["status"] == "verified"]
    return {
        "schema": "debot4.grok_profile_verification_summary.v1",
        "generated_at": datetime.now(UTC),
        "lead_handles": lead_count,
        "verified_profiles": len(verified),
        "profile_unavailable": len(rows) - len(verified),
        "unique_stable_user_ids": len({row["profile_user_id"] for row in verified}),
        "warning": "A verified profile is an account candidate, not proof of KOL quality.",
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append")
    parser.add_argument("--output", default="grok_chinese_profile_verified.jsonl")
    parser.add_argument("--summary", default="grok_chinese_profile_summary.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    args.input = args.input or ["grok_chinese_kol_leads.jsonl"]
    if not 1 <= args.workers <= 12:
        parser.error("workers must be between 1 and 12")
    return args


if __name__ == "__main__":
    main()
