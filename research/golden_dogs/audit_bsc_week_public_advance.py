#!/usr/bin/env python3
"""Join reviewed public events to transaction-level first 1.02 crossings."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.event_time_capture import (
    AdvanceLane, PublicAdvanceEvent, assess_public_event_time, lead_time_bucket,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
TRADES = ROOT / "bsc_week_trade_price_evidence.jsonl"
X = ROOT / "bsc_week_x_exact_semantic_evidence.jsonl"
TG = ROOT / "bsc_week_telegram_evidence.jsonl"
PROJECT = ROOT / "bsc_week_project_advance_reviews.jsonl"
OUTPUT = ROOT / "bsc_week_public_advance_audit.jsonl"
LATENCIES = (0, 5, 15, 30, 60, 120)
FORWARD_X = frozenset(("own_position", "market_thesis", "bare_call"))


def main() -> None:
    events = _events()
    rows = [_wave(row, events.get(row["label"], ())) for row in _jsonl(TRADES)]
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 waves, got {len(rows)}")
    write_jsonl(OUTPUT, rows)
    write_json(ROOT / "bsc_week_public_advance_audit_summary.json", _summary(rows))


def _events():
    grouped = {}
    seen = set()
    included_x_tweets = set()
    for row in _jsonl(X):
        if row["semantic"] not in FORWARD_X:
            continue
        if row["origin"] not in {"independent", "project"}:
            raise RuntimeError(
                f"forward X origin is not eligible: {row['tweet_id']}:{row['address']}"
            )
        lane = (AdvanceLane.PROJECT if row["origin"] == "project"
                else AdvanceLane.INDEPENDENT)
        event = PublicAdvanceEvent(
            "x_exact", f"x:{row['tweet_id']}:{row['address']}",
            _at(row["published_at"]), lane, True, True,
        )
        _add(grouped, seen, row["label"], event)
        included_x_tweets.add((row["label"], row["tweet_id"]))
    for row in _jsonl(PROJECT):
        if (row["label"], row["tweet_id"]) in included_x_tweets:
            continue
        event = PublicAdvanceEvent(
            "x_project", f"x-project:{row['tweet_id']}",
            _at(row["occurred_at"]), AdvanceLane.PROJECT, True, True,
        )
        _add(grouped, seen, row["label"], event)
    for row in _jsonl(TG):
        if row["status"] != "direct_verified" or not row["created_at"]:
            continue
        lane = (AdvanceLane.INDEPENDENT if row["independent_forward_signal"]
                else AdvanceLane.RELAY)
        event = PublicAdvanceEvent(
            "telegram", f"tg:{row['channel']}:{row['message_id']}",
            _at(row["created_at"]), lane,
            bool(row["exact_ca_literal_or_url"]),
            bool(row["independent_forward_signal"]),
        )
        _add(grouped, seen, row["label"], event)
    return {label: tuple(items) for label, items in grouped.items()}


def _add(grouped, seen, label, event):
    key = (label, event.event_id)
    if key in seen:
        return
    seen.add(key)
    grouped.setdefault(label, []).append(event)


def _wave(row, events):
    small = _crossing(row, "1.02")
    assessments = {}
    if small is not None:
        for latency in LATENCIES:
            assessments[str(latency)] = [
                _assessment(event, int(row["fresh_signal_start"]), small, latency)
                for event in events
            ]
    return {
        "schema": "debot4.bsc_week_public_advance_audit.v1",
        "label": row["label"], "address": row["address"],
        "wave_number": row["wave_number"],
        "fresh_signal_start": row["fresh_signal_start"],
        "first_1_02_at": small,
        "event_time_assessments": assessments,
        "warning": "counterfactual event-time ceiling; live first-seen was not observed",
    }


def _summary(rows):
    coverage = {}
    for latency in LATENCIES:
        key = str(latency)
        coverage[key] = {}
        for lane in AdvanceLane:
            coverage[key][lane.value] = sum(any(
                item["event_time_actionable"] and item["lane"] == lane.value
                for item in row["event_time_assessments"].get(key, ())
            ) for row in rows)
        coverage[key]["any_public"] = sum(any(
            item["event_time_actionable"]
            for item in row["event_time_assessments"].get(key, ())
        ) for row in rows)
        coverage[key]["fresh_any_public"] = sum(any(
            item["event_time_actionable"]
            and item["freshness"] == "fresh_pre_motion"
            for item in row["event_time_assessments"].get(key, ())
        ) for row in rows)
    zero = [
        item for row in rows
        for item in row["event_time_assessments"].get("0", ())
        if item["event_time_actionable"]
    ]
    unique_events = {
        (row["label"], item["event_id"])
        for row in rows
        for item in row["event_time_assessments"].get("0", ())
    }
    closest = []
    for row in rows:
        actionable = [item for item in row["event_time_assessments"].get("0", ())
                      if item["event_time_actionable"]]
        if actionable:
            closest.append(min(actionable, key=lambda item: item["seconds_to_first_1_02"]))
    return {
        "schema": "debot4.bsc_week_public_advance_audit_summary.v2",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows), "event_time_coverage": coverage,
        "zero_latency_actionable_wave_event_association_lane_counts": dict(sorted(Counter(
            item["lane"] for item in zero
        ).items())),
        "unique_input_event_count": len(unique_events),
        "zero_latency_closest_lead_bucket_wave_counts": dict(sorted(Counter(
            lead_time_bucket(int(item["seconds_to_first_1_02"])) for item in closest
        ).items())),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (TRADES, X, TG, PROJECT)
        },
        "output_sha256": hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),
        "warnings": (
            "Published-at event timing is a counterfactual subscription ceiling, not observed live capture.",
            "Publisher/KOL historical selectivity and control-universe precision remain unqualified.",
            "Project-action exact-CA binding comes from reviewed token-account metadata; "
            "the action need not contain a literal CA.",
            "Telegram pair URLs are excluded until pair-to-exact-CA binding is independently resolved.",
        ),
    }


def _assessment(event, fresh_start, small, latency):
    item = asdict(assess_public_event_time(
        event, fresh_start=fresh_start, first_1_02_at=small,
        assumed_latency_seconds=latency,
    ))
    item["lane"] = item["lane"].value
    if item["freshness"] is not None:
        item["freshness"] = item["freshness"].value
    item["occurred_at"] = event.occurred_at
    item["evidence_url"] = _evidence_url(event.event_id)
    return item


def _evidence_url(event_id):
    parts = event_id.split(":")
    if parts[0] == "x" and len(parts) >= 2:
        return f"https://x.com/i/status/{parts[1]}"
    if parts[0] == "x-project" and len(parts) == 2:
        return f"https://x.com/i/status/{parts[1]}"
    if parts[0] == "tg" and len(parts) == 3:
        return f"https://t.me/{parts[1]}/{parts[2]}"
    raise ValueError(f"unsupported public event id: {event_id}")


def _crossing(row, multiple):
    found = next((step for step in row["transaction_price_ladder"]
                  if step["multiple"] == multiple), None)
    return None if not found or not found["crossing"] else int(
        found["crossing"]["occurred_at"]
    )


def _at(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
