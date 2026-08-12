#!/usr/bin/env python3
"""Verify X profiles for model-transcribed Tintin directory entries."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
SOURCE_STATUS = "https://x.com/Tintinx2021/status/1978501606682558735"
SOURCE_AUTHOR_ID = "1516629293505277953"
SOURCE_IMAGE = "https://pbs.twimg.com/media/G3UMuGhbAAMG4vb.jpg?name=orig"
SOURCE_IMAGE_SHA256 = "036e1221c9a5b507d5cb05caa5b9d743beb4952338462d63ddd77007403a5d1f"


def main() -> None:
    args = _args()
    entries, response_id = _entries(ROOT / args.input)
    rows: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {pool.submit(_verify, entry, response_id): entry for entry in entries}
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            print(f"{row['claimed_handle']} {row['status']}", flush=True)
    rows.sort(key=lambda row: str(row["claimed_handle"]).casefold())
    write_jsonl(ROOT / args.output, rows)
    write_json(ROOT / args.summary, _summary(rows, response_id))


def _entries(path: Path) -> tuple[tuple[dict[str, object], ...], str]:
    recovered = json.loads(path.read_text(encoding="utf-8"))
    answer = recovered.get("answer")
    if recovered.get("grok_is_evidence") is not False or not isinstance(answer, str):
        raise ValueError("directory transcription must be a non-evidentiary Grok lead")
    payload = json.loads(answer)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("directory transcription has no entries")
    clean: list[dict[str, object]] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        handle = str(entry.get("handle") or "").strip().lstrip("@")
        key = handle.casefold()
        if not HANDLE.fullmatch(handle) or key in seen:
            continue
        seen.add(key)
        clean.append({**entry, "handle": handle})
    return tuple(clean), str(recovered.get("response_id") or "")


def _verify(entry: dict[str, object], response_id: str) -> dict[str, object]:
    handle = str(entry["handle"])
    base: dict[str, object] = {
        "schema": "debot4.tintin_directory_profile.v1",
        "claimed_handle": handle,
        "claimed_display_name": entry.get("display_name"),
        "directory_section": entry.get("image_section"),
        "directory_role_claim": entry.get("probable_role"),
        "directory_role_basis": entry.get("role_basis"),
        "source_status_url": SOURCE_STATUS,
        "source_author_id": SOURCE_AUTHOR_ID,
        "source_image_url": SOURCE_IMAGE,
        "source_image_sha256": SOURCE_IMAGE_SHA256,
        "transcription_response_id": response_id,
        "directory_is_kol_proof": False,
    }
    try:
        observation = XProfileClient().fetch_observation(handle)
        return {
            **base,
            "status": "verified",
            "verified_at": datetime.now(UTC),
            "profile": asdict(observation.profile),
            "profile_source_url": observation.source_url,
            "profile_response_bytes": observation.response_bytes,
            "profile_payload_sha256": observation.sha256,
            "profile_response_identity": observation.response_identity,
        }
    except Exception as exc:
        return {
            **base,
            "status": "profile_unavailable",
            "verified_at": datetime.now(UTC),
            "error_type": type(exc).__name__,
        }


def _summary(rows: list[dict[str, object]], response_id: str) -> dict[str, object]:
    verified = [row for row in rows if row["status"] == "verified"]
    sections: dict[str, int] = {}
    for row in verified:
        section = str(row.get("directory_section") or "unknown")
        sections[section] = sections.get(section, 0) + 1
    return {
        "schema": "debot4.tintin_directory_profile_summary.v1",
        "generated_at": datetime.now(UTC),
        "transcription_response_id": response_id,
        "transcribed_handles": len(rows),
        "verified_profiles": len(verified),
        "profile_unavailable": len(rows) - len(verified),
        "unique_stable_user_ids": len({
            str(row["profile"]["user_id"]) for row in verified
        }),
        "verified_by_directory_section": dict(sorted(sections.items())),
        "warning": "Directory membership and profile verification do not prove KOL quality",
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="grok_tintin_directory_recovered.json")
    parser.add_argument("--output", default="tintin_directory_profiles.jsonl")
    parser.add_argument("--summary", default="tintin_directory_profile_summary.json")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("workers must be between 1 and 12")
    return args


if __name__ == "__main__":
    main()
