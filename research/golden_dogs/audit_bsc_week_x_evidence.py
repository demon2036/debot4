#!/usr/bin/env python3
"""Build one strict Exact-CA X evidence ledger for the fixed BSC week."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.narrative.fxtwitter import FxTwitterClient, parse_x_status_url


ROOT = Path(__file__).resolve().parent
WINDOW_START = datetime(2026, 8, 6, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 13, tzinfo=timezone.utc)
MANUAL = ROOT / "bsc_week_x_manual_candidates.json"
SOURCES = (
    ROOT / "grok_chinese_x_verified.jsonl",
    ROOT / "grok_bsc_market_x_verified.jsonl",
    ROOT / "grok_tintin_x_verified.jsonl",
    ROOT / "grok_chinese_profile_deep_x_verified.jsonl",
    ROOT / "grok_chinese_profile_frontier2_x_verified.jsonl",
)


def main() -> None:
    targets = _targets()
    rows = _existing_rows(targets)
    manual = json.loads(MANUAL.read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=6) as pool:
        pending = {pool.submit(_fetch_manual, item): item for item in manual}
        for future in as_completed(pending):
            row = future.result()
            rows[_row_key(row)] = row
            print(f"verified {row['label']} {row['status_url']}", flush=True)
    ordered = sorted(rows.values(), key=lambda row: (
        str(row["published_at"]), str(row["status_url"]), str(row["address"]),
    ))
    _validate_coverage(ordered, targets)
    output = ROOT / "bsc_week_x_exact_evidence.jsonl"
    write_jsonl(output, ordered)
    counts = {
        label: sum(row["label"] == label for row in ordered)
        for label in targets.values()
    }
    write_json(ROOT / "bsc_week_x_exact_evidence_summary.json", {
        "schema": "debot4.bsc_week_x_exact_evidence_summary.v1",
        "window": {"start": WINDOW_START, "end_exclusive": WINDOW_END},
        "target_count": len(targets),
        "verified_exact_ca_association_count": len(ordered),
        "unique_verified_post_count": len({row["tweet_id"] for row in ordered}),
        "counts_by_label": counts,
        "source_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in (*SOURCES, MANUAL)
        },
        "warning": (
            "Each row proves an authored X post containing the literal Exact CA. "
            "It does not by itself prove that the post caused a price move; Grok "
            "was used only for discovery and is not treated as evidence."
        ),
    })
    print(f"wrote {len(ordered)} strict posts for {len(targets)} targets")


def _targets() -> dict[str, str]:
    targets: dict[str, str] = {}
    path = ROOT / "bsc_week_wave_replays.jsonl"
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        targets[str(row["address"]).casefold()] = str(row["label"])
    if len(targets) != 13:
        raise RuntimeError("expected exactly 13 replay targets")
    return targets


def _existing_rows(targets: dict[str, str]) -> dict[str, dict[str, object]]:
    accepted: dict[str, dict[str, object]] = {}
    for path in SOURCES:
        for line in path.read_text(encoding="utf-8").splitlines():
            source = json.loads(line)
            if source.get("status") != "verified":
                continue
            published = _time(str(source.get("published_at") or ""))
            if not WINDOW_START <= published < WINDOW_END:
                continue
            text = str(source.get("text") or "")
            matches = [address for address in targets if address in text.casefold()]
            for address in matches:
                row = _from_source(source, path.name, address, targets[address])
                accepted.setdefault(_row_key(row), row)
    return accepted


def _from_source(
    source: dict[str, object], source_file: str, address: str, label: str,
) -> dict[str, object]:
    required = (
        "status_url", "published_at", "observed_handle", "text",
        "status_payload_sha256", "status_response_bytes", "status_response_identity",
    )
    if any(not source.get(field) for field in required):
        raise RuntimeError(f"strict source row missing receipt fields in {source_file}")
    url = str(source["status_url"])
    handle, tweet_id = parse_x_status_url(url)
    canonical = str(source.get("canonical_url") or url)
    if _tweet_id(canonical) != tweet_id:
        raise RuntimeError(f"status identity mismatch: {url}")
    text = str(source["text"])
    if address not in text.casefold():
        raise RuntimeError(f"Exact CA disappeared from source row: {url}")
    return {
        "schema": "debot4.bsc_week_x_exact_evidence.v1",
        "label": label, "address": address, "tweet_id": tweet_id,
        "author_handle": str(source["observed_handle"]),
        "author_id": source.get("observed_author_id"),
        "published_at": source["published_at"], "status_url": canonical,
        "text": text, "text_sha256": sha256(text.encode()).hexdigest(),
        "status_payload_sha256": source["status_payload_sha256"],
        "status_response_bytes": source["status_response_bytes"],
        "status_response_identity": source["status_response_identity"],
        "status_fetched_at": source.get("status_fetched_at"),
        "evidence_source": source_file, "exact_ca_literal": True,
        "provider_direct_verified": True, "grok_is_evidence": False,
    }


def _fetch_manual(item: dict[str, object]) -> dict[str, object]:
    address = str(item["address"]).casefold()
    observation = FxTwitterClient(timeout_seconds=20).fetch_observation(
        str(item["status_url"])
    )
    tweet = observation.tweet
    if not WINDOW_START <= tweet.published_at < WINDOW_END:
        raise RuntimeError(f"manual post outside fixed window: {tweet.canonical_url}")
    if address not in tweet.text.casefold():
        raise RuntimeError(f"manual post lacks literal Exact CA: {tweet.canonical_url}")
    return {
        "schema": "debot4.bsc_week_x_exact_evidence.v1",
        "label": str(item["label"]), "address": address,
        "tweet_id": tweet.tweet_id, "author_handle": tweet.author_handle,
        "author_id": tweet.author_id, "published_at": tweet.published_at,
        "status_url": tweet.canonical_url, "text": tweet.text,
        "text_sha256": sha256(tweet.text.encode()).hexdigest(),
        "status_payload_sha256": sha256(observation.raw_payload).hexdigest(),
        "status_response_bytes": len(observation.raw_payload),
        "status_response_identity": observation.response_identity,
        "status_fetched_at": tweet.fetched_at,
        "evidence_source": MANUAL.name, "lead_note": item.get("lead_note"),
        "exact_ca_literal": True, "provider_direct_verified": True,
        "grok_is_evidence": False,
    }


def _validate_coverage(rows: list[dict[str, object]], targets: dict[str, str]) -> None:
    covered = {str(row["address"]) for row in rows}
    missing = set(targets) - covered
    if missing:
        raise RuntimeError(f"targets lacking strict Exact-CA X posts: {sorted(missing)}")


def _tweet_id(url: str) -> str:
    return parse_x_status_url(url)[1]


def _row_key(row: dict[str, object]) -> str:
    return f"{row['tweet_id']}:{row['address']}"


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


if __name__ == "__main__":
    main()
