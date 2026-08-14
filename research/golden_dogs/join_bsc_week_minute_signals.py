#!/usr/bin/env python3
"""Join chain, Exact-CA X, and social evidence to conservative 1m stages."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.minute_breakout import (
    MinuteWaveBoundary,
    PriceCrossing,
)
from debot4.v6.golden_dogs.minute_signal_timing import classify_minute_signal
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
MINUTE = ROOT / "bsc_week_minute_wave_replays.jsonl"
FIVE_MINUTE = ROOT / "bsc_week_wave_replays.jsonl"
AUDIT = ROOT / "bsc_gmgn_kol_audit_v2.jsonl"
QUALIFICATION = ROOT / "bsc_gmgn_qualification.jsonl"
X_EVIDENCE = ROOT / "bsc_week_x_exact_semantic_evidence.jsonl"
SOCIAL = ROOT / "bsc_week_wave_social_joins.jsonl"
LANES = ("chain_tagged", "chain_clean", "x_exact", "social_eligible")
FORWARD_X = frozenset(("own_position", "market_thesis", "bare_call"))


def main() -> None:
    minutes = _keyed(MINUTE, wave=True)
    replays = _keyed(FIVE_MINUTE)
    audits = _keyed(AUDIT)
    qualifications = _keyed(QUALIFICATION)
    x_posts = _x_by_address()
    social = _keyed(SOCIAL, wave=True)
    rows: list[dict[str, object]] = []
    for key, minute in minutes.items():
        address, number = key
        replay = replays[address]
        previous_reset = _previous_effective_reset(replay, number)
        fresh_start = max(int(replay["created_at"]), previous_reset or 0)
        boundary = _boundary(minute["boundary"])
        clean_hashes = {
            str(item["transaction_hash"]).casefold()
            for item in qualifications[address].get("clean_buys", ())
        }
        buys = _chain_events(audits[address], clean_hashes, fresh_start, boundary)
        x_events = _x_events(x_posts.get(address, ()), fresh_start, boundary)
        social_events = _social_events(social[key], fresh_start, boundary)
        lanes = {
            "chain_tagged": _lane(tuple(item for item in buys if item["tagged"])),
            "chain_clean": _lane(tuple(item for item in buys if item["clean"])),
            "x_exact": _lane(x_events),
            "social_eligible": _lane(social_events),
        }
        rows.append({
            "schema": "debot4.bsc_week_minute_signal_join.v1",
            "label": minute["label"], "address": address,
            "wave_number": number, "fresh_signal_start": fresh_start,
            "fresh_signal_rule": (
                "first wave: token creation; later waves: previous effective "
                "wave reset candle start"
            ),
            "boundary": minute["boundary"], "lanes": lanes,
            "any_strict_advance": any(lanes[name]["strict_count"] for name in LANES),
            "any_early_advance": any(lanes[name]["early_count"] for name in LANES),
        })
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    if len(rows) != 32:
        raise RuntimeError(f"expected 32 minute joins, got {len(rows)}")
    output = ROOT / "bsc_week_minute_signal_joins.jsonl"
    write_jsonl(output, rows)
    write_json(ROOT / "bsc_week_minute_signal_join_summary.json", _summary(rows, output))
    print(f"joined {len(rows)} minute waves")


def _chain_events(audit, clean_hashes, fresh_start, boundary):
    events = []
    for item in audit.get("verified_kol_buys", ()):
        trade = item["provider_trade"]
        at = int(trade["timestamp"])
        if not fresh_start <= at < boundary.wave_end_exclusive:
            continue
        tx_hash = str(trade["transaction_hash"]).casefold()
        price = Decimal(str(trade["price_usd"]))
        events.append({
            "occurred_at": at, "stage": asdict(classify_minute_signal(at, boundary)),
            "price_usd": price,
            "price_multiple_from_baseline": price / boundary.baseline_price_usd,
            "below_motion_price": price < boundary.baseline_price_usd * Decimal("1.2"),
            "below_breakout_price": price < boundary.baseline_price_usd * 2,
            "tagged": True, "clean": tx_hash in clean_hashes,
            "wallet": trade["wallet"], "x_handle": trade.get("x_handle"),
            "tags": trade.get("tags", ()), "amount_usd": trade["amount_usd"],
            "transaction_hash": tx_hash,
            "rpc_receipt_sha256": item["rpc_swap"]["receipt"]["sha256"],
        })
    return tuple(sorted(events, key=lambda item: (item["occurred_at"], item["transaction_hash"])))


def _x_events(posts, fresh_start, boundary):
    events = []
    for post in posts:
        at = _time(post["published_at"])
        if fresh_start <= at < boundary.wave_end_exclusive:
            events.append({
                "occurred_at": at,
                "stage": asdict(classify_minute_signal(at, boundary)),
                "author_handle": post["author_handle"],
                "semantic": post["semantic"], "origin": post["origin"],
                "status_url": post["status_url"],
                "text_sha256": post["text_sha256"],
                "tweet_id": post["tweet_id"],
                "payload_sha256": post["status_payload_sha256"],
            })
    return tuple(events)


def _social_events(row, fresh_start, boundary):
    events = []
    seen = set()
    for phase in ("historical_baseline", "pre_trough", "ascent", "decay", "later"):
        for event in row[phase]:
            if not event["causal_timing_eligible"]:
                continue
            at = _time(event["occurred_at"])
            identity = (event["source_kind"], event["status_url"], at)
            if identity in seen or not fresh_start <= at < boundary.wave_end_exclusive:
                continue
            seen.add(identity)
            events.append({
                **event, "occurred_at": at,
                "stage": asdict(classify_minute_signal(at, boundary)),
            })
    return tuple(sorted(events, key=lambda item: item["occurred_at"]))


def _lane(events):
    strict = tuple(item for item in events if item["stage"]["strict_advance"])
    early = tuple(item for item in events if item["stage"]["early_advance"])
    return {
        "event_count": len(events), "strict_count": len(strict),
        "early_count": len(early), "events": events,
        "earliest_strict": strict[0] if strict else None,
        "earliest_early": early[0] if early else None,
    }


def _summary(rows, output):
    return {
        "schema": "debot4.bsc_week_minute_signal_join_summary.v1",
        "target_count": len({row["address"] for row in rows}),
        "wave_count": len(rows),
        "waves_with_any_strict_advance": sum(row["any_strict_advance"] for row in rows),
        "waves_with_any_early_advance": sum(row["any_early_advance"] for row in rows),
        "lane_wave_coverage": {
            name: {
                "strict": sum(bool(row["lanes"][name]["strict_count"]) for row in rows),
                "early": sum(bool(row["lanes"][name]["early_count"]) for row in rows),
            } for name in LANES
        },
        "source_sha256": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in (MINUTE, FIVE_MINUTE, AUDIT, QUALIFICATION, X_EVIDENCE, SOCIAL, output)
        },
        "scope_warning": (
            "Chain events are GMGN KOL-filtered provider rows verified on BSC RPC, "
            "not the full smart-wallet universe. Exact-X is restricted to the "
            "98-association manual semantic ledger's forward classes. Social "
            "eligible includes "
            "direct forward Telegram and linked-account exact-time actions."
        ),
        "timing_warning": (
            "Only events before a crossing candle start count. Events inside its "
            "minute are ambiguous and excluded from strict/early advance coverage."
        ),
    }


def _boundary(row):
    def crossing(value):
        return None if value is None else PriceCrossing(
            multiple=Decimal(str(value["multiple"])),
            threshold_price_usd=Decimal(str(value["threshold_price_usd"])),
            crossing_bar_at=int(value["crossing_bar_at"]),
            crossing_before=int(value["crossing_before"]),
            crossing_end_exclusive=int(value["crossing_end_exclusive"]),
            first_close_confirmed_at=value["first_close_confirmed_at"],
        )
    return MinuteWaveBoundary(
        wave_start=int(row["wave_start"]),
        trough_end_exclusive=int(row["trough_end_exclusive"]),
        wave_end_exclusive=int(row["wave_end_exclusive"]),
        interval_seconds=int(row["interval_seconds"]), candle_count=int(row["candle_count"]),
        baseline_price_usd=Decimal(str(row["baseline_price_usd"])),
        baseline_fdv_usd=Decimal(str(row["baseline_fdv_usd"])),
        baseline_bar_at=int(row["baseline_bar_at"]),
        baseline_established_at=int(row["baseline_established_at"]),
        baseline_source=str(row["baseline_source"]), motion=crossing(row["motion"]),
        breakout=crossing(row["breakout"]), peak_high_at=int(row["peak_high_at"]),
        peak_high_price_usd=Decimal(str(row["peak_high_price_usd"])),
    )


def _previous_effective_reset(replay, number):
    effective = [item for item in replay["completed_swings"] if item["effective"]]
    return None if number == 1 else int(effective[number - 2]["reset_at"])


def _x_by_address():
    grouped = {}
    for row in _jsonl(X_EVIDENCE):
        if row["semantic"] not in FORWARD_X:
            continue
        grouped.setdefault(str(row["address"]).casefold(), []).append(row)
    return {key: tuple(sorted(value, key=lambda row: row["published_at"]))
            for key, value in grouped.items()}


def _keyed(path, wave=False):
    rows = _jsonl(path)
    if wave:
        return {(str(row["address"]).casefold(), int(row["wave_number"])): row for row in rows}
    return {str(row["address"]).casefold(): row for row in rows}


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _time(value):
    return int(datetime.fromisoformat(str(value).replace("Z", "+00:00"))
               .astimezone(timezone.utc).timestamp())


if __name__ == "__main__":
    main()
