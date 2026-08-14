#!/usr/bin/env python3
"""Join linked-account actions and direct Telegram posts to all 32 waves."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from debot4.v6.golden_dogs.market_waves import wave_phase_bounds
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
REPLAYS = ROOT / "bsc_week_wave_replays.jsonl"
PROFILES = ROOT / "bsc_week_x_account_profiles.jsonl"
ACTIONS = ROOT / "bsc_week_x_account_actions.jsonl"
TELEGRAM = ROOT / "bsc_week_telegram_evidence.jsonl"


def main() -> None:
    events = _events_by_label()
    rows: list[dict[str, object]] = []
    for replay in _jsonl(REPLAYS):
        label = str(replay["label"])
        target_events = events.get(label, ())
        effective = [wave for wave in replay["completed_swings"] if wave["effective"]]
        for number, wave in enumerate(effective, 1):
            bounds = wave_phase_bounds(
                window_start=int(replay["window_start"]),
                window_end_exclusive=int(replay["window_end_exclusive"]),
                trough_at=int(wave["trough_at"]),
                peak_at=int(wave["peak_at"]),
                reset_at=int(wave["reset_at"]),
            )
            rows.append({
                "schema": "debot4.bsc_week_wave_social_join.v1",
                "label": label,
                "address": replay["address"],
                "wave_number": number,
                "wave": wave,
                "historical_baseline": _select(
                    target_events, bounds.historical_start,
                    bounds.pre_trough_start, bounds.trough_start,
                ),
                "pre_trough": _select(
                    target_events, bounds.pre_trough_start,
                    bounds.trough_start, bounds.trough_start,
                ),
                "ascent": _select(
                    target_events, bounds.trough_start,
                    bounds.peak_end_exclusive, bounds.trough_start,
                ),
                "decay": _select(
                    target_events, bounds.peak_end_exclusive,
                    bounds.reset_end_exclusive, bounds.trough_start,
                ),
                "later": _select(
                    target_events, bounds.reset_end_exclusive,
                    bounds.window_end_exclusive, bounds.trough_start,
                ),
            })
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 wave rows, got {len(rows)}")
    write_jsonl(ROOT / "bsc_week_wave_social_joins.jsonl", rows)
    _write_summary(rows, events)
    print(f"joined account/Telegram evidence to {len(rows)} waves")


def _events_by_label() -> dict[str, tuple[dict[str, object], ...]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in _jsonl(PROFILES):
        for event in _profile_events(row):
            for label in row["labels"]:
                grouped.setdefault(str(label), []).append(event)
    for row in _jsonl(ACTIONS):
        if not row["exact_action_time_available"]:
            continue
        event = {
            "source_kind": "x_linked_account_action",
            "occurred_at": row["original_status_created_at"],
            "temporal_precision": "exact_status_time",
            "causal_timing_eligible": True,
            "actor": row["timeline_actor"],
            "action_kind": row["action_kind"],
            "status_url": row["status_url"],
            "text": row["text"],
            "media_urls": row["media_urls"],
            "payload_sha256": row["timeline_payload_sha256"],
        }
        for label in row["labels"]:
            grouped.setdefault(str(label), []).append(event)
    for row in _jsonl(TELEGRAM):
        if row["status"] != "direct_verified":
            continue
        event = {
            "source_kind": "telegram_direct_message",
            "occurred_at": row["created_at"],
            "temporal_precision": "exact_message_time",
            "causal_timing_eligible": bool(row["independent_forward_signal"]),
            "actor": row["channel"],
            "action_kind": row["semantic"],
            "status_url": row["canonical_url"],
            "text": row["text"],
            "independent_forward_signal": row["independent_forward_signal"],
            "payload_sha256": row["raw_payload_sha256"],
        }
        grouped.setdefault(str(row["label"]), []).append(event)
    return {
        label: tuple(sorted(found, key=lambda row: str(row["occurred_at"])))
        for label, found in grouped.items()
    }


def _profile_events(row: dict[str, object]) -> list[dict[str, object]]:
    if row["status"] != "verified_current_snapshot":
        return []
    common = {
        "source_kind": "x_linked_account_profile_event",
        "actor": row["handle"],
        "status_url": row["source_url"],
        "payload_sha256": row["payload_sha256"],
    }
    events = [{
        **common,
        "occurred_at": row["joined_at"],
        "temporal_precision": "exact_account_creation_time",
        "causal_timing_eligible": True,
        "action_kind": "account_created",
    }]
    for field, kind in (
        ("avatar_resource_at", "avatar_resource_timestamp"),
        ("banner_resource_at", "banner_resource_timestamp"),
    ):
        if row.get(field):
            events.append({
                **common,
                "occurred_at": row[field],
                "temporal_precision": "current_asset_resource_indicator",
                "causal_timing_eligible": False,
                "action_kind": kind,
                "warning": row["resource_time_warning"],
            })
    return events


def _select(
    events: tuple[dict[str, object], ...], start: int, end: int, trough: int,
) -> list[dict[str, object]]:
    selected = []
    for event in events:
        timestamp = int(_time(str(event["occurred_at"])).timestamp())
        if start <= timestamp < end:
            selected.append({**event, "seconds_from_trough": timestamp - trough})
    return selected


def _write_summary(rows, events) -> None:
    all_events = [event for found in events.values() for event in found]
    write_json(ROOT / "bsc_week_wave_social_join_summary.json", {
        "schema": "debot4.bsc_week_wave_social_join_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "unique_labeled_event_count": len(all_events),
        "waves_with_causal_timing_eligible_pre_or_ascent": sum(
            any(event["causal_timing_eligible"] for phase in ("pre_trough", "ascent")
                for event in row[phase]) for row in rows
        ),
        "source_sha256": {
            path.name: sha256(path.read_bytes()).hexdigest()
            for path in (REPLAYS, PROFILES, ACTIONS, TELEGRAM)
        },
        "warning": (
            "Profile asset resource times are indicators, not proven UI action times. "
            "Linked-account proximity and Telegram proximity do not prove causation."
        ),
    })


def _jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


if __name__ == "__main__":
    main()
