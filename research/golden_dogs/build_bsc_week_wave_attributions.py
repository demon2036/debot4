#!/usr/bin/env python3
"""Bind all 32 manual causal reviews to immutable market/social/chain evidence."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.event_time_capture import lead_time_bucket
from debot4.v6.golden_dogs.narrative_source_audit import (
    build_narrative_source_audit, narrative_target_counts,
)
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.wave_attribution import validate_wave_reviews, wave_key


ROOT = Path(__file__).resolve().parent
INPUTS = {
    "reviews": ROOT / "bsc_week_wave_attribution_reviews.jsonl",
    "replays": ROOT / "bsc_week_wave_replays.jsonl",
    "chain": ROOT / "bsc_week_wave_chain_joins.jsonl",
    "trade": ROOT / "bsc_week_trade_price_evidence.jsonl",
    "public": ROOT / "bsc_week_public_advance_audit.jsonl",
    "blocks": ROOT / "bsc_week_uncovered_pre_breakout_blocks.jsonl",
    "x_join": ROOT / "bsc_week_wave_x_joins.jsonl",
    "social": ROOT / "bsc_week_wave_social_joins.jsonl",
    "minute": ROOT / "bsc_week_minute_wave_replays.jsonl",
    "semantics": ROOT / "bsc_week_x_exact_semantic_evidence.jsonl",
    "narratives": ROOT / "bsc_week_x_narrative_sources.jsonl",
}
OUTPUT = ROOT / "bsc_week_wave_attributions.jsonl"
SUMMARY = ROOT / "bsc_week_wave_attribution_summary.json"
PHASES = ("historical_baseline", "pre_trough", "ascent", "decay", "later")


def main() -> None:
    data = {name: _jsonl(path) for name, path in INPUTS.items()}
    chain = _unique(data["chain"])
    expected = set(chain)
    validate_wave_reviews(data["reviews"], expected)
    indexed = {
        name: _unique(rows) for name, rows in data.items()
        if name in {"trade", "public", "x_join", "social", "minute"}
    }
    blocks = _unique(data["blocks"])
    semantics = {row["status_url"]: row for row in data["semantics"]}
    narrative = _narratives(data["narratives"])
    replays = {row["label"]: row for row in data["replays"]}
    rows = []
    for review in data["reviews"]:
        key = wave_key(review)
        rows.append(_build(
            review, chain[key], indexed["trade"][key], indexed["public"][key],
            blocks.get(key), indexed["x_join"][key], indexed["social"][key],
            indexed["minute"][key], semantics,
            narrative.get(review["label"], ()), replays[review["label"]],
        ))
    rows.sort(key=lambda row: (row["address"], row["wave_number"]))
    _audit(rows, expected)
    write_jsonl(OUTPUT, rows)
    write_json(SUMMARY, _summary(rows))


def _build(review, chain, trade, public, block, x_join, social, minute,
           semantics, narrative, replay):
    advance = [item for item in public["event_time_assessments"]["0"]
               if item["event_time_actionable"]]
    fresh = [item for item in advance if item["freshness"] == "fresh_pre_motion"]
    standing = [item for item in advance if item["freshness"] == "standing_pre_wave"]
    closest = min(advance, key=lambda item: item["seconds_to_first_1_02"], default=None)
    x_events = _x_events(x_join, semantics)
    social_events = _social_events(social)
    narrative_audit = build_narrative_source_audit(
        upstream_sources=narrative,
        x_evidence_by_phase=x_events,
        manual_conclusion=review["narrative_source"],
        token_created_at=int(replay["created_at"]),
    )
    first_small = _crossing(trade, "1.02")
    first_large = _crossing(trade, "1.20")
    flow = trade["pre_motion_buy_flow"][-1] if trade["pre_motion_buy_flow"] else None
    result = {
        "schema": "debot4.bsc_week_wave_attribution.v2",
        "label": review["label"], "address": chain["address"],
        "wave_number": review["wave_number"], "market": {
            **chain["wave"], "first_1_02": first_small,
            "first_1_20": first_large, "fixed_window_ath_proxy": replay["ath"],
            "token_created_at": replay["created_at"],
            "minute_boundary": minute["boundary"],
        },
        "advance_public": {
            "zero_latency_actionable_count": len(advance),
            "fresh_count": len(fresh), "standing_count": len(standing),
            "fresh_events": fresh, "standing_events": standing,
            "closest_event": closest,
            "closest_lead_seconds": (
                None if closest is None else closest["seconds_to_first_1_02"]
            ),
            "closest_lead_bucket": (
                None if closest is None else lead_time_bucket(
                    int(closest["seconds_to_first_1_02"])
                )
            ),
            "counterfactual_only": True,
        },
        "chain_evidence": {
            "pre_trough": _chain_phase(chain["pre_trough"]),
            "ascent": _chain_phase(chain["ascent"]),
            "observed_pre_1_20_buy_flow": flow,
            "strict_pre_1_02_block_buys": [] if block is None else block["buys"],
            "qualification_outcome": chain["qualification_outcome"],
            "qualification_reasons": chain["qualification_reasons"],
        },
        "narrative_evidence": narrative,
        "narrative_source_audit": narrative_audit,
        "x_evidence_by_phase": x_events,
        "social_evidence_by_phase": social_events,
        "manual_review": {key: value for key, value in review.items()
                          if key not in {"label", "wave_number"}},
    }
    result["capture_class"] = _capture_class(result, block)
    return result


def _capture_class(row, block):
    advance = row["advance_public"]
    if advance["zero_latency_actionable_count"]:
        return "public_before_1_02"
    buys = () if block is None else block["buys"]
    if any(item["block_timing"]["post_confirmation_actionable"] for item in buys):
        return "previous_block_only_before_1_02"
    return "same_block_pending_or_builder_only"


def _x_events(join, semantics):
    output = {}
    for phase in PHASES:
        output[phase] = []
        for event in join[phase]:
            semantic = semantics.get(event["status_url"], {})
            output[phase].append({
                "occurred_at": event["published_at"],
                "actor": event["author_handle"],
                "semantic": semantic.get("semantic", "missing_manual_semantic"),
                "url": event["status_url"],
                "payload_sha256": event["status_payload_sha256"],
            })
    return output


def _social_events(join):
    output = {}
    for phase in PHASES:
        output[phase] = [{
            "occurred_at": event["occurred_at"], "actor": event["actor"],
            "source_kind": event["source_kind"], "action_kind": event["action_kind"],
            "causal_timing_eligible": event["causal_timing_eligible"],
            "url": event["status_url"], "payload_sha256": event["payload_sha256"],
        } for event in join[phase]]
    return output


def _chain_phase(phase):
    return {
        key: phase[key] for key in (
            "start", "end_exclusive", "tagged_buy_count", "tagged_wallet_count",
            "tagged_amount_usd", "clean_buy_count", "clean_wallet_count",
            "clean_amount_usd", "earliest_clean", "largest_clean",
        )
    }


def _crossing(row, multiple):
    item = next(step for step in row["transaction_price_ladder"]
                if step["multiple"] == multiple)
    return item["crossing"]


def _narratives(rows):
    grouped = {}
    for row in rows:
        compact = {key: row.get(key) for key in (
            "status", "published_at", "author_handle", "relation", "status_url",
            "metadata_link_is_endorsement", "payload_sha256",
        )}
        for label in row["labels"]:
            grouped.setdefault(label, []).append(compact)
    return {key: tuple(value) for key, value in grouped.items()}


def _audit(rows, expected):
    keys = [wave_key(row) for row in rows]
    if len(rows) != 32 or len({row["address"] for row in rows}) != 13:
        raise RuntimeError("attribution ledger must contain exactly 13 targets / 32 waves")
    if set(keys) != expected or len(keys) != len(set(keys)):
        raise RuntimeError("attribution output coverage mismatch")
    if any(event["semantic"] == "missing_manual_semantic" for row in rows
           for phase in PHASES for event in row["x_evidence_by_phase"][phase]):
        raise RuntimeError("joined X evidence is missing a manual semantic review")


def _summary(rows):
    return {
        "schema": "debot4.bsc_week_wave_attribution_summary.v2",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "capture_class_counts": dict(sorted(Counter(
            row["capture_class"] for row in rows).items())),
        "public_closest_lead_bucket_counts": dict(sorted(Counter(
            row["advance_public"]["closest_lead_bucket"] for row in rows
            if row["advance_public"]["closest_lead_bucket"] is not None
        ).items())),
        "best_supported_driver_counts": dict(sorted(Counter(
            row["manual_review"]["best_supported_driver"] for row in rows).items())),
        "confidence_counts": dict(sorted(Counter(
            row["manual_review"]["confidence"] for row in rows).items())),
        "narrative_source_target_counts": narrative_target_counts(rows),
        "source_sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in INPUTS.values()},
        "warnings": (
            "Attribution is the best-supported mechanism, not proof of causation.",
            "Published-at public coverage is a counterfactual ceiling, not observed live capture.",
            "Current supply times 5m high is an FDV proxy, not executable market cap.",
            "No wallet or KOL in this winner-only audit passed point-in-time skill qualification.",
        ),
    }


def _unique(rows):
    result = {}
    for row in rows:
        key = wave_key(row)
        if key in result:
            raise ValueError(f"duplicate source wave: {key}")
        result[key] = row
    return result


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(
        encoding="utf-8",
    ).splitlines() if line.strip()]


if __name__ == "__main__":
    main()
