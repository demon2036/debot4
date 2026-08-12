#!/usr/bin/env python3
"""Independently verify direct X status leads emitted by any Grok scan."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.grok_journal import (
    reusable_x_verification_rows,
    successful_candidate_urls,
)
from debot4.v6.narrative.actor_evidence import (
    ActorEvidenceCandidate,
    verify_actor_evidence,
)
from debot4.v6.narrative.fxtwitter import (
    FxTwitterClient,
    FxTwitterError,
    FxTwitterObservation,
    parse_x_status_url,
)
from debot4.v6.x import XProfile
from debot4.v6.x.profile import XProfileClient, XProfileObservation


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    args = _args()
    leads = _leads(ROOT / args.input)
    output = ROOT / args.output
    cached = _cached_rows(output, leads, args.schema)
    pending_leads = tuple(url for url in leads if url not in cached)
    profiles = _profiles(pending_leads, args.workers)
    rows = list(cached.values())
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {
            pool.submit(_verify, url, profiles, args.schema): url
            for url in pending_leads
        }
        for future in as_completed(pending):
            row = future.result()
            rows.append(row)
            print(f"{row['status_url']} {row['status']}", flush=True)
    rows.sort(key=lambda item: str(item["status_url"]))
    write_jsonl(output, rows)
    write_json(ROOT / args.summary, _summary(
        rows, len(leads), schema=args.summary_schema,
    ))


def _leads(path: Path) -> tuple[str, ...]:
    urls = set()
    values = successful_candidate_urls(
        path.read_text(encoding="utf-8").splitlines(),
    )
    for value in values:
        try:
            handle, status_id = parse_x_status_url(value)
        except FxTwitterError:
            continue
        urls.add(f"https://x.com/{handle}/status/{status_id}")
    return tuple(sorted(urls))


def _cached_rows(
    path: Path, leads: tuple[str, ...], schema: str,
) -> dict[str, dict[str, object]]:
    if not path.exists():
        return {}
    return reusable_x_verification_rows(
        path.read_text(encoding="utf-8").splitlines(),
        desired_urls=leads,
        schema=schema,
    )


class _CachedProfiles:
    def __init__(
        self,
        observations: Mapping[str, XProfileObservation],
        errors: Mapping[str, str],
    ) -> None:
        self.observations = observations
        self.errors = errors

    def fetch(self, handle: str) -> XProfile:
        key = handle.casefold()
        observation = self.observations.get(key)
        if observation is None:
            raise RuntimeError(self.errors.get(key, "profile was not prefetched"))
        return observation.profile


class _CapturingStatuses:
    def __init__(self) -> None:
        self.observation: FxTwitterObservation | None = None

    def fetch_status(self, status_url: str):
        self.observation = FxTwitterClient().fetch_observation(status_url)
        return self.observation.tweet


def _profiles(leads: tuple[str, ...], workers: int) -> _CachedProfiles:
    handles = tuple(sorted({parse_x_status_url(url)[0].casefold() for url in leads}))
    observations: dict[str, XProfileObservation] = {}
    errors: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {pool.submit(_profile, handle): handle for handle in handles}
        for future in as_completed(pending):
            handle = pending[future]
            try:
                observations[handle] = future.result()
            except Exception as exc:
                errors[handle] = type(exc).__name__
    return _CachedProfiles(observations, errors)


def _profile(handle: str) -> XProfileObservation:
    return XProfileClient().fetch_observation(handle)


def _verify(
    url: str, profiles: _CachedProfiles, schema: str,
) -> dict[str, object]:
    handle, _ = parse_x_status_url(url)
    statuses = _CapturingStatuses()
    finding = verify_actor_evidence(
        ActorEvidenceCandidate(handle, url),
        profiles=profiles,
        statuses=statuses,
    )
    row = asdict(finding)
    row.update({
        "schema": schema,
        "verified_at": datetime.now(UTC),
        "text_sha256": sha256(finding.text.encode("utf-8")).hexdigest()
        if finding.text else None,
    })
    status = statuses.observation
    if status is not None:
        row.update({
            "published_at": status.tweet.published_at,
            "status_fetched_at": status.tweet.fetched_at,
            "status_response_bytes": len(status.raw_payload),
            "status_payload_sha256": sha256(status.raw_payload).hexdigest(),
            "status_response_identity": status.response_identity,
        })
    profile = profiles.observations.get(handle.casefold())
    if profile is not None:
        row.update({
            "profile_handle": profile.profile.handle,
            "profile_display_name": profile.profile.display_name,
            "profile_description": profile.profile.description,
            "profile_source_url": profile.source_url,
            "profile_fetched_at": profile.profile.fetched_at,
            "profile_response_bytes": profile.response_bytes,
            "profile_payload_sha256": profile.sha256,
            "profile_response_identity": profile.response_identity,
        })
    return row


def _summary(
    rows: list[dict], lead_count: int, *, schema: str,
) -> dict[str, object]:
    counts: dict[str, int] = {}
    for row in rows:
        status = str(row["status"])
        counts[status] = counts.get(status, 0) + 1
    return {
        "schema": schema,
        "generated_at": datetime.now(UTC),
        "lead_count": lead_count,
        "unique_profile_count": len({
            str(row["profile_user_id"])
            for row in rows
            if row.get("status") == "verified" and row.get("profile_user_id")
        }),
        "status_counts": dict(sorted(counts.items())),
        "warning": "verified means X identity and authored post only, not KOL quality or wallet",
    }


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--input", default="grok_chinese_kol_leads.jsonl")
    parser.add_argument("--output", default="grok_chinese_x_verified.jsonl")
    parser.add_argument("--summary", default="grok_chinese_x_verification_summary.json")
    parser.add_argument("--schema", default="debot4.grok_chinese_x_verification.v1")
    parser.add_argument(
        "--summary-schema",
        default="debot4.grok_chinese_x_verification_summary.v1",
    )
    args = parser.parse_args()
    if not 1 <= args.workers <= 12:
        parser.error("workers must be between 1 and 12")
    return args


if __name__ == "__main__":
    main()
