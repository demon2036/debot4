#!/usr/bin/env python3
"""Verify token-metadata narrative sources without treating links as endorsements."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.narrative.fxtwitter import (
    FxTwitterClient,
    FxTwitterError,
    parse_x_status_url,
)


ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "bsc_week_x_source_candidates.json"


def main() -> None:
    candidates = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    rows = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {pool.submit(_fetch, item): item for item in candidates}
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            print(f"{row['status']}: {row['status_url']}", flush=True)
    rows.sort(key=lambda row: str(row.get("published_at") or row["status_url"]))
    write_jsonl(ROOT / "bsc_week_x_narrative_sources.jsonl", rows)
    write_json(ROOT / "bsc_week_x_narrative_sources_summary.json", {
        "schema": "debot4.bsc_week_x_narrative_sources_summary.v1",
        "candidate_count": len(candidates),
        "verified_count": sum(row["status"] == "verified" for row in rows),
        "unavailable_count": sum(row["status"] == "unavailable" for row in rows),
        "source_sha256": {CANDIDATES.name: sha256(CANDIDATES.read_bytes()).hexdigest()},
        "warning": (
            "A token page citing a status proves metadata association only. It does "
            "not prove the source author knew, endorsed, or referred to the Exact CA."
        ),
    })


def _fetch(item: dict[str, object]) -> dict[str, object]:
    url = str(item["status_url"])
    _, expected_id = parse_x_status_url(url)
    try:
        observation = FxTwitterClient(timeout_seconds=20).fetch_observation(url)
    except FxTwitterError as exc:
        return {
            "schema": "debot4.bsc_week_x_narrative_source.v1",
            **item,
            "tweet_id": expected_id,
            "status": "unavailable",
            "provider_direct_verified": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
    tweet = observation.tweet
    if tweet.tweet_id != expected_id:
        raise RuntimeError(f"source identity mismatch: {url}")
    return {
        "schema": "debot4.bsc_week_x_narrative_source.v1",
        **item,
        "tweet_id": tweet.tweet_id,
        "status": "verified",
        "author_handle": tweet.author_handle,
        "author_id": tweet.author_id,
        "published_at": tweet.published_at,
        "fetched_at": tweet.fetched_at,
        "canonical_url": tweet.canonical_url,
        "text": tweet.text,
        "text_sha256": sha256(tweet.text.encode()).hexdigest(),
        "payload_sha256": sha256(observation.raw_payload).hexdigest(),
        "response_bytes": len(observation.raw_payload),
        "response_identity": observation.response_identity,
        "provider_direct_verified": True,
        "metadata_link_is_endorsement": False,
    }


if __name__ == "__main__":
    main()
