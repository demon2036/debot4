#!/usr/bin/env python3
"""Snapshot linked X accounts and paginate their full fixed-week timelines."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping
import urllib.parse

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.x import FxJsonHttp, FxTwitterError
from debot4.v6.x.forensic import (
    XForensicAction,
    parse_forensic_profile,
    parse_forensic_timeline_page,
)


ROOT = Path(__file__).resolve().parent
CONFIG = ROOT / "bsc_week_x_accounts.json"
WINDOW_START = datetime(2026, 8, 6, tzinfo=timezone.utc)
WINDOW_END = datetime(2026, 8, 13, tzinfo=timezone.utc)
MAX_PAGES = 8


def main() -> None:
    configs = json.loads(CONFIG.read_text(encoding="utf-8"))
    profiles, actions, pages = [], [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(_audit, item): item for item in configs}
        for future in as_completed(pending):
            profile, found, receipts = future.result()
            profiles.append(profile)
            actions.extend(found)
            pages.extend(receipts)
            print(
                f"{profile['handle']}: {profile['status']}, {len(found)} actions",
                flush=True,
            )
    profiles.sort(key=lambda row: str(row["handle"]).casefold())
    actions.sort(key=lambda row: (
        str(row["timeline_actor"]), str(row["original_status_created_at"]),
        str(row["tweet_id"]),
    ))
    pages.sort(key=lambda row: (str(row["handle"]), int(row["page_number"])))
    write_jsonl(ROOT / "bsc_week_x_account_profiles.jsonl", profiles)
    write_jsonl(ROOT / "bsc_week_x_account_actions.jsonl", actions)
    write_jsonl(ROOT / "bsc_week_x_account_page_receipts.jsonl", pages)
    _summary(configs, profiles, actions, pages)
    print(f"wrote {len(actions)} fixed-week account actions")


def _audit(item: dict[str, object]) -> tuple[dict, list[dict], list[dict]]:
    handle = str(item["handle"])
    expected_id = item.get("expected_user_id")
    if not expected_id:
        return _unavailable_profile(item), [], []
    http = FxJsonHttp(timeout_seconds=20)
    profile_url = f"https://api.fxtwitter.com/{urllib.parse.quote(handle, safe='')}"
    document = http.get_json(profile_url)
    if document is None:
        raise RuntimeError(f"empty profile for {handle}")
    profile = parse_forensic_profile(
        document.payload,
        expected_handle=handle,
        expected_user_id=str(expected_id),
        fetched_at=document.fetched_at,
    )
    profile_row = {
        "schema": "debot4.bsc_week_x_account_profile.v1",
        **asdict(profile),
        "labels": item["labels"],
        "association": item["association"],
        "status": "verified_current_snapshot",
        "source_url": profile_url,
        "response_bytes": document.response_bytes,
        "payload_sha256": document.sha256,
        "response_identity": document.response_identity,
        "resource_time_warning": (
            "avatar/banner resource time is decoded from the current asset URL; it "
            "does not preserve the previous image or independently prove UI action time"
        ),
    }
    actions, pages = _timeline(http, item, str(expected_id))
    return profile_row, actions, pages


def _timeline(
    http: FxJsonHttp, item: dict[str, object], expected_id: str,
) -> tuple[list[dict], list[dict]]:
    handle = str(item["handle"])
    cursor = ""
    seen: set[str] = set()
    selected: dict[str, dict] = {}
    pages = []
    reached_start = False
    for page_number in range(1, MAX_PAGES + 1):
        query = {"count": 100}
        if cursor:
            query["cursor"] = cursor
        url = (
            f"https://api.fxtwitter.com/2/profile/"
            f"{urllib.parse.quote(handle, safe='')}/statuses?{urllib.parse.urlencode(query)}"
        )
        document = http.get_json(url)
        if document is None:
            raise RuntimeError(f"empty timeline page for {handle}")
        page = parse_forensic_timeline_page(
            document.payload,
            expected_handle=handle,
            expected_user_id=expected_id,
            fetched_at=document.fetched_at,
        )
        pages.append(_page_receipt(handle, page_number, url, document, page))
        page_keys = {action.tweet_id for action in page.actions}
        made_progress = bool(page_keys - seen)
        for action in page.actions:
            _accept_action(selected, seen, action, item, document, url, page_number)
        dates = [action.original_status_created_at for action in page.actions]
        reached_start = bool(dates) and min(dates) < WINDOW_START
        if (
            reached_start
            or not page.bottom_cursor
            or page.bottom_cursor == cursor
            or (page_number > 1 and not made_progress)
        ):
            break
        cursor = page.bottom_cursor
    if not reached_start and cursor and len(pages) == MAX_PAGES:
        raise RuntimeError(f"timeline page cap reached before fixed-window start: {handle}")
    return list(selected.values()), pages


def _accept_action(
    selected: dict[str, dict],
    seen: set[str],
    action: XForensicAction,
    item: dict[str, object],
    document,
    url: str,
    page_number: int,
) -> None:
    key = action.tweet_id
    seen.add(key)
    if not WINDOW_START <= action.original_status_created_at < WINDOW_END:
        return
    previous = selected.get(key)
    if previous and previous["exact_action_time_available"]:
        return
    row = {
        "schema": "debot4.bsc_week_x_account_action.v1",
        **asdict(action),
        "status_url": action.canonical_url,
        "labels": item["labels"],
        "association": item["association"],
        "timeline_page_number": page_number,
        "timeline_source_url": url,
        "timeline_payload_sha256": document.sha256,
        "timeline_response_bytes": document.response_bytes,
        "timeline_response_identity": document.response_identity,
        "repost_time_warning": (
            "original_status_created_at is not repost time"
            if action.action_kind == "repost_snapshot" else None
        ),
    }
    selected[key] = row


def _page_receipt(handle, number, url, document, page) -> dict[str, object]:
    return {
        "schema": "debot4.bsc_week_x_account_page_receipt.v1",
        "handle": handle.lower(),
        "page_number": number,
        "source_url": url,
        "fetched_at": document.fetched_at,
        "response_bytes": document.response_bytes,
        "payload_sha256": document.sha256,
        "response_identity": document.response_identity,
        "result_count": page.result_count,
        "bottom_cursor_sha256": (
            sha256(page.bottom_cursor.encode()).hexdigest() if page.bottom_cursor else None
        ),
    }


def _unavailable_profile(item: dict[str, object]) -> dict[str, object]:
    handle = str(item["handle"])
    url = f"https://api.fxtwitter.com/{urllib.parse.quote(handle, safe='')}"
    try:
        FxJsonHttp(timeout_seconds=20).get_json(url)
    except FxTwitterError as exc:
        error_type = type(exc).__name__
        error = str(exc)
    else:
        raise RuntimeError(f"unreviewed account became available: {handle}")
    return {
        "schema": "debot4.bsc_week_x_account_profile.v1",
        "handle": handle.lower(),
        "labels": item["labels"],
        "association": item["association"],
        "status": "unavailable_at_fetch",
        "source_url": url,
        "error_type": error_type,
        "error": error,
        "historical_content_verified": False,
    }


def _summary(configs, profiles, actions, pages) -> None:
    direct = [row for row in actions if row["exact_action_time_available"]]
    reposts = [row for row in actions if row["action_kind"] == "repost_snapshot"]
    write_json(ROOT / "bsc_week_x_account_actions_summary.json", {
        "schema": "debot4.bsc_week_x_account_actions_summary.v1",
        "window": {"start": WINDOW_START, "end_exclusive": WINDOW_END},
        "configured_account_count": len(configs),
        "verified_profile_count": sum(row["status"].startswith("verified") for row in profiles),
        "unavailable_profile_count": sum(row["status"].startswith("unavailable") for row in profiles),
        "timeline_page_count": len(pages),
        "fixed_week_action_count": len(actions),
        "direct_timed_action_count": len(direct),
        "repost_snapshot_count": len(reposts),
        "labels_with_direct_actions": sorted({label for row in direct for label in row["labels"]}),
        "source_sha256": {CONFIG.name: sha256(CONFIG.read_bytes()).hexdigest()},
        "warning": (
            "Current profiles cannot prove prior bios. Asset resource times do not "
            "preserve old images. Repost snapshots expose original-post time, not repost time."
        ),
    })


if __name__ == "__main__":
    main()
