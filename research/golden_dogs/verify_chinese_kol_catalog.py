#!/usr/bin/env python3
"""Freeze public X receipts for the reviewed Chinese meme-KOL catalog."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from debot4.v6.golden_dogs.kol_identity import (
    CHINESE_MEME_KOL_CANDIDATES,
    LOOKONCHAIN_BSC_TRADERS,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.narrative.fxtwitter import FxTwitterClient
from debot4.v6.x.profile import XProfileClient


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc
SOURCE_POSTS = (
    ("lookonchain-wallet-attribution", "https://x.com/lookonchain/status/1975782365650952370"),
    ("facai-community-directory", "https://x.com/facai988/status/1982437570467504565"),
    ("mintclub-corroboration", "https://x.com/Mintclub002/status/1985234545114030477"),
    ("gcsheng-exact-ca-post", "https://x.com/GCsheng/status/2064388171040010417"),
)


def main() -> None:
    identities = LOOKONCHAIN_BSC_TRADERS + CHINESE_MEME_KOL_CANDIDATES
    with ThreadPoolExecutor(max_workers=8) as pool:
        pending = {pool.submit(_profile, item): item.handle for item in identities}
        profiles = [future.result() for future in as_completed(pending)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        pending = {
            pool.submit(_source, purpose, url): purpose for purpose, url in SOURCE_POSTS
        }
        sources = [future.result() for future in as_completed(pending)]
    profiles.sort(key=lambda row: str(row["configured_handle"]).casefold())
    sources.sort(key=lambda row: str(row["purpose"]))
    write_jsonl(ROOT / "chinese_kol_profiles.jsonl", profiles)
    write_jsonl(ROOT / "chinese_kol_sources.jsonl", sources)
    write_json(ROOT / "chinese_kol_catalog_summary.json", _summary(profiles, sources))


def _profile(identity) -> dict[str, object]:
    try:
        observation = XProfileClient().fetch_observation(identity.handle)
        profile = observation.profile
        stable_id_match = profile.user_id == identity.stable_user_id
        return {
            "schema": "debot4.chinese_kol_profile.v1",
            "status": "verified" if stable_id_match else "stable_id_mismatch",
            "configured_handle": identity.handle,
            "configured_user_id": identity.stable_user_id,
            "configured_tier": identity.tier,
            "configured_aliases": identity.aliases,
            "observed_profile": profile,
            "stable_id_match": stable_id_match,
            "source_url": observation.source_url,
            "response_bytes": observation.response_bytes,
            "payload_sha256": observation.sha256,
            "response_identity": observation.response_identity,
        }
    except Exception as exc:
        return {
            "schema": "debot4.chinese_kol_profile.v1",
            "status": "error",
            "configured_handle": identity.handle,
            "configured_user_id": identity.stable_user_id,
            "error_type": type(exc).__name__,
        }


def _source(purpose: str, url: str) -> dict[str, object]:
    try:
        observation = FxTwitterClient().fetch_observation(url)
        return {
            "schema": "debot4.chinese_kol_source.v1",
            "status": "verified",
            "purpose": purpose,
            "tweet": observation.tweet,
            "payload_sha256": sha256(observation.raw_payload).hexdigest(),
            "response_bytes": len(observation.raw_payload),
            "response_identity": observation.response_identity,
        }
    except Exception as exc:
        return {
            "schema": "debot4.chinese_kol_source.v1",
            "status": "error",
            "purpose": purpose,
            "source_url": url,
            "error_type": type(exc).__name__,
        }


def _summary(profiles: list[dict], sources: list[dict]) -> dict[str, object]:
    return {
        "schema": "debot4.chinese_kol_catalog_summary.v1",
        "generated_at": datetime.now(UTC),
        "configured_identities": len(profiles),
        "verified_profiles": sum(row["status"] == "verified" for row in profiles),
        "profile_errors": sum(row["status"] == "error" for row in profiles),
        "stable_id_mismatches": sum(
            row["status"] == "stable_id_mismatch" for row in profiles
        ),
        "source_posts": len(sources),
        "verified_source_posts": sum(row["status"] == "verified" for row in sources),
    }


if __name__ == "__main__":
    main()
