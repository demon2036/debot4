#!/usr/bin/env python3
"""Build the auditable theoretical-versus-implemented capture conclusion."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json


ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "bsc_week_public_advance_audit_summary.json"
BLOCKS = ROOT / "bsc_week_uncovered_pre_breakout_blocks_summary.json"
OUTCOMES = ROOT / "bsc_week_selective_wallet_outcomes_summary.json"
PROFILES = ROOT / "bsc_week_all_x_wallet_profiles_summary.json"
ONLINE = ROOT / "bsc_week_online_capture_audit_summary.json"
OUTPUT = ROOT / "bsc_week_theoretical_capture_summary.json"
LATENCIES = (0, 5, 15, 30, 60, 120)


def main() -> None:
    public, blocks = _json(PUBLIC), _json(BLOCKS)
    outcomes, profiles = _json(OUTCOMES), _json(PROFILES)
    online = _json(ONLINE)
    normal = {
        str(value): int(blocks["public_or_normal_confirmation_timing_ceiling"][str(value)])
        for value in LATENCIES
    }
    payload = {
        "schema": "debot4.bsc_week_theoretical_capture_summary.v1",
        "target_count": 13, "wave_count": 32,
        "advance_boundary": (
            "An event is advance only if machine-observable before the first exact "
            "transaction reaches 1.02x the retrospective wave baseline."
        ),
        "winning_wave_recall_ceiling": {
            "public_published_at_event_time": int(
                public["event_time_coverage"]["0"]["any_public"]
            ),
            "fresh_current_wave_public_event": int(
                public["event_time_coverage"]["0"]["fresh_any_public"]
            ),
            "public_closest_lead_bucket_wave_counts": dict(
                public["zero_latency_closest_lead_bucket_wave_counts"]
            ),
            "normal_confirmation_public_union_by_latency_seconds": normal,
            "reactive_1_02_before_1_20_by_latency_seconds": {
                str(value): int(online["early_1_02_detection_upper_bound"][str(value)])
                for value in LATENCIES
            },
            "same_block_builder_or_mempool_only": int(blocks["same_block_only_wave_count"]),
            "ideal_zero_latency_pending_or_builder_union": int(
                blocks["ideal_mempool_or_builder_order_ceiling_at_zero_latency"]
            ),
        },
        "qualification": {
            "historical_x_attributed_wallet_leads": int(profiles["candidate_count"]),
            "frequency_screen_pass_wallets": int(outcomes["wallet_count"]),
            "mature_wallet_token_outcomes": int(outcomes["mature_outcome_count"]),
            "measurable_wallet_token_outcomes": int(outcomes["measurable_outcome_count"]),
            "early_gold_hits": int(outcomes["hit_count"]),
            "skill_screen_pass_wallets": int(outcomes["skill_screen_pass_count"]),
            "point_in_time_qualified_kols_or_wallets": 0,
            "wallet_screen_results": tuple({
                "x_handle": row["x_handle"],
                "wallet": row["wallet"],
                "measurable_tokens": row["measurable_tokens"],
                "hits": row["hits"], "hit_rate": row["hit_rate"],
                "skill_screen_pass": row["skill_screen_pass"],
            } for row in outcomes["wallet_assessments"]),
        },
        "current_runtime": {
            "implemented_full_bsc_pending_or_builder_subscription": False,
            "implemented_all_launch_transaction_stream": False,
            "market_monitor": (
                "CMC exact BSC 1h gainer polling every 5s; minimum +3%, "
                "$25k liquidity, $5k 1h volume, and 4 transactions."
            ),
            "historical_observed_first_seen_evidence_complete": False,
            "can_claim_32_of_32_advance_capture_now": False,
        },
        "conclusions": {
            "ideal_raw_event_visibility": "32/32 only under zero-latency pending/builder access",
            "ordinary_post_confirmation_ceiling_at_zero_latency": "27/32",
            "ordinary_post_confirmation_ceiling_at_five_seconds": "24/32",
            "qualified_predictive_advance_signals": "0/32",
            "guarantee_scope": (
                "Completeness can be guaranteed only for configured observable feeds; "
                "private/deleted social events and private bundles are outside that scope."
            ),
        },
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (PUBLIC, BLOCKS, OUTCOMES, PROFILES, ONLINE)
        },
        "warnings": (
            "Winning-wave recall does not estimate false positives or profitability.",
            "Published-at times are counterfactual subscription ceilings, not actual historical first-seen logs.",
            "Seeing an early buy is not evidence that the buyer was skilled or worth copying.",
            "Replay fresh/standing is a state boundary, not a proxy for signal recency; use explicit lead-time buckets.",
        ),
    }
    write_json(OUTPUT, payload)


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
