#!/usr/bin/env python3
"""Rank public actors that were strictly visible before transaction-level +2%."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.advance_actor import summarize_advance_actors
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "bsc_week_public_advance_audit.jsonl"
SEMANTICS = ROOT / "bsc_week_x_exact_semantic_evidence.jsonl"
PROJECT = ROOT / "bsc_week_project_advance_reviews.jsonl"
TELEGRAM = ROOT / "bsc_week_telegram_evidence.jsonl"
OUTPUT = ROOT / "bsc_week_advance_actor_leads.jsonl"
SUMMARY = ROOT / "bsc_week_advance_actor_leads_summary.json"


def main() -> None:
    metadata = _metadata()
    events = []
    for wave in _jsonl(PUBLIC):
        for item in wave["event_time_assessments"]["0"]:
            if not item["event_time_actionable"]:
                continue
            meta = metadata.get(item["event_id"])
            if meta is None:
                raise RuntimeError(f"public event metadata missing: {item['event_id']}")
            events.append({
                **meta, "label": wave["label"],
                "wave_number": int(wave["wave_number"]),
                "lead_seconds": int(item["seconds_to_first_1_02"]),
                "freshness": item["freshness"],
            })
    rows = list(summarize_advance_actors(events))
    _audit(rows, events)
    write_jsonl(OUTPUT, rows)
    write_json(SUMMARY, {
        "schema": "debot4.bsc_week_advance_actor_leads_summary.v1",
        "actor_count": len(rows), "event_wave_association_count": len(events),
        "covered_wave_count": len({
            (item["label"], item["wave_number"]) for item in events
        }),
        "independent_actor_count": sum(
            row["source"] in {"x_independent", "telegram_independent"} for row in rows
        ),
        "project_actor_count": sum(row["source"] == "x_project" for row in rows),
        "repeat_advance_actor_count": sum(row["advance_wave_count"] >= 2 for row in rows),
        "repeat_fresh_advance_actor_count": sum(
            row["fresh_advance_wave_count"] >= 2 for row in rows
        ),
        "cross_target_advance_actor_count": sum(row["target_count"] >= 2 for row in rows),
        "qualified_kol_count": 0,
        "qualification_warning": (
            "Every row is a discovery lead. Winner-only timing cannot establish "
            "KOL skill, selectivity, false-positive rate, wallet control, or profitability."
        ),
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (PUBLIC, SEMANTICS, PROJECT, TELEGRAM, OUTPUT)
        },
    })


def _metadata():
    result = {}
    for row in _jsonl(SEMANTICS):
        event_id = f"x:{row['tweet_id']}:{row['address']}"
        if row["origin"] not in {"project", "independent"}:
            if row["semantic"] in {"own_position", "market_thesis", "bare_call"}:
                raise RuntimeError(f"forward X origin is not eligible: {event_id}")
            continue
        source = f"x_{row['origin']}"
        result[event_id] = {
            "source": source, "actor": row["author_handle"],
            "occurred_at": _at(row["published_at"]), "url": row["status_url"],
            "semantic": row["semantic"], "origin": row["origin"],
            "payload_sha256": row["status_payload_sha256"],
        }
    actions = {
        str(row["tweet_id"]): row
        for row in _jsonl(ROOT / "bsc_week_x_account_actions.jsonl")
    }
    for row in _jsonl(PROJECT):
        event_id = f"x-project:{row['tweet_id']}"
        action = actions.get(str(row["tweet_id"]))
        if action is None:
            raise RuntimeError(f"project action missing for {event_id}")
        result[event_id] = {
            "source": "x_project", "actor": action["timeline_actor"],
            "occurred_at": _at(row["occurred_at"]),
            "url": f"https://x.com/i/status/{row['tweet_id']}",
            "semantic": row["semantic"], "origin": "project",
            "payload_sha256": action["timeline_payload_sha256"],
        }
    for row in _jsonl(TELEGRAM):
        if row.get("status") != "direct_verified" or not row.get("created_at"):
            continue
        event_id = f"tg:{row['channel']}:{row['message_id']}"
        result[event_id] = {
            "source": "telegram_independent", "actor": row["channel"],
            "occurred_at": _at(row["created_at"]), "url": row["canonical_url"],
            "semantic": row["semantic"], "origin": "independent",
            "payload_sha256": row["raw_payload_sha256"],
        }
    return result


def _audit(rows, events):
    if len({(item["label"], item["wave_number"]) for item in events}) != 21:
        raise RuntimeError("advance actor ledger must cover exactly 21 public waves")
    if any(row["qualification_status"] != "discovery_lead_only" for row in rows):
        raise RuntimeError("actor lead was improperly promoted")
    if any(
        item["lead_seconds"] <= 0 or not item["url"]
        or not isinstance(item["payload_sha256"], str)
        or len(item["payload_sha256"]) != 64
        for item in events
    ):
        raise RuntimeError("advance actor receipt is incomplete")


def _at(value):
    return int(datetime.fromisoformat(str(value).replace("Z", "+00:00"))
               .astimezone(timezone.utc).timestamp())


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
