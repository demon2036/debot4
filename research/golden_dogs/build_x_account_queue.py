#!/usr/bin/env python3
"""Build one evidence-first X account queue without promoting leads to actors."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_account_queue import (
    XAccountEvidence,
    XAccountRole,
    assess_x_account_queue,
)
from debot4.v6.narrative.actor_catalog import DEFAULT_ACTOR_CATALOG
from debot4.v6.narrative.actors import ActorTier


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    joins = _joined_x_markets()
    profiles = _profiles()
    wallet_evidence = _wallet_evidence()
    rank_evidence = _rank_evidence()
    reviews = {row["stable_user_id"]: row for row in _json("x_account_role_reviews.json")}
    accounts = _accounts(joins, profiles, wallet_evidence, rank_evidence)
    rows = [_row(identity, accounts[identity], profiles.get(identity),
                 wallet_evidence.get(identity, ()), rank_evidence.get(identity, ()),
                 reviews.get(identity)) for identity in sorted(accounts)]
    rows.sort(key=lambda row: (
        not row["has_pre_peak_exact_ca_post"],
        not row["reviewed_role"], -int(row["pre_peak_post_token_count"]),
        str(row["handle"]),
    ))
    write_jsonl(ROOT / "x_account_candidate_queue.jsonl", rows)
    write_jsonl(ROOT / "x_pre_peak_account_queue.jsonl", (
        row for row in rows if row["has_pre_peak_exact_ca_post"]
    ))
    write_json(ROOT / "x_account_candidate_summary.json", _summary(rows, reviews))


def _accounts(joins, profiles, wallets, ranks) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = defaultdict(lambda: {
        "eligible_tokens": set(), "pre_peak_tokens": set(), "posts": [],
        "source_kinds": set(),
    })
    seen_posts: set[tuple[str, str]] = set()
    for join in joins:
        x, market = join["x"], join["market"]
        post_key = (str(x["status_url"]), str(market["address"]).lower())
        if post_key in seen_posts:
            continue
        seen_posts.add(post_key)
        identity = str(x["stable_user_id"])
        item = output[identity]
        item["source_kinds"].add("verified_exact_ca_x_post")
        item["eligible_tokens"].add(str(market["address"]))
        if join["timing"] == "pre_peak":
            item["pre_peak_tokens"].add(str(market["address"]))
        item["posts"].append({
            "status_url": x["status_url"], "address": market["address"],
            "published_at": x["published_at"], "peak_at": market["peak_at"],
            "timing": join["timing"], "text": x["text"],
        })
    for source, label in ((wallets, "gmgn_rpc_wallet_x_binding"),
                          (ranks, "gmgn_rank_wallet_x_binding")):
        for identity in source:
            output[identity]["source_kinds"].add(label)
    for actor in DEFAULT_ACTOR_CATALOG:
        for identity in actor.author_ids:
            output[identity]["source_kinds"].add("reviewed_actor_catalog")
            output[identity]["actor"] = actor
    for identity in profiles:
        output[identity]["source_kinds"].add("verified_x_profile")
    return output


def _row(identity, item, profile, wallets, ranks, review) -> dict[str, object]:
    actor = item.get("actor")
    role = XAccountRole(review["role"]) if review else _catalog_role(actor)
    handle = (profile or {}).get("handle") or (actor.handle if actor else "")
    display = (profile or {}).get("display_name") or (actor.display_name if actor else "")
    tokens, early = item["eligible_tokens"], item["pre_peak_tokens"]
    evidence = XAccountEvidence(
        handle=str(handle), stable_user_id=identity, display_name=str(display),
        source_kinds=tuple(item["source_kinds"]), eligible_token_count=len(tokens),
        pre_peak_post_token_count=len(early), wallet_binding_pass=bool(wallets or ranks),
        provider_high_frequency=any(row["provider_high_frequency"] for row in ranks),
    )
    assessment = assess_x_account_queue(evidence, reviewed_role=role)
    posts = sorted(item["posts"], key=lambda row: (row["published_at"], row["address"]))
    return {
        "schema": "debot4.x_account_candidate.v1", **asdict(evidence),
        "profile": profile, "reviewed_role": role.value if role else None,
        "role_review": review, "catalog_tier": actor.tier.value if actor else None,
        "monitor_candidate": assessment.monitor_candidate,
        "smart_wallet_candidate": assessment.smart_wallet_candidate,
        "reasons": assessment.reasons, "has_pre_peak_exact_ca_post": bool(early),
        "wallet_bindings": (*wallets, *ranks),
        "sample_pre_peak_posts": [row for row in posts if row["timing"] == "pre_peak"][:5],
        "sample_post_peak_posts": [row for row in posts if row["timing"] == "post_peak"][:3],
        "warning": "candidate is not an active actor, origin claim, or profitable wallet",
    }


def _profiles() -> dict[str, dict[str, object]]:
    output = {}
    for name in ("grok_bsc_market_x_verified.jsonl",
                 "grok_x_account_identity_verified.jsonl",
                 "grok_wallet_x_identity_verified.jsonl",
                 "grok_chinese_x_verified.jsonl"):
        for row in _optional_jsonl(name):
            if row.get("status") != "verified" or not row.get("profile_user_id"):
                continue
            output[str(row["profile_user_id"])] = {
                "handle": row.get("profile_handle"),
                "display_name": row.get("profile_display_name"),
                "description": row.get("profile_description"),
                "source_url": row.get("profile_source_url"),
                "payload_sha256": row.get("profile_payload_sha256"),
            }
    for row in _jsonl("chinese_kol_profiles.jsonl"):
        profile = row.get("observed_profile") or {}
        if row.get("status") == "verified":
            output[str(profile["user_id"])] = {
                **profile, "source_url": row.get("source_url"),
                "payload_sha256": row.get("payload_sha256"),
            }
    return output


def _wallet_evidence() -> dict[str, tuple[dict[str, object], ...]]:
    output: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _jsonl("bsc_audit_wallet_x_verified.jsonl"):
        binding = row.get("x_binding") or {}
        if binding.get("verdict") != "PASS":
            continue
        output[str(binding["stable_user_id"])].append({
            "source": "gmgn_rpc_audit", "wallet": row["wallet"],
            "eligible_buy_token_count": row["eligible_token_count"],
            "pre_peak_buy_token_count": row["pre_peak_token_count"],
            "buy_transaction_count": row["buy_transaction_count"],
            "provider_tags": row["provider_tags"], "provider_high_frequency": False,
        })
    return {key: tuple(value) for key, value in output.items()}


def _rank_evidence() -> dict[str, tuple[dict[str, object], ...]]:
    output: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in _jsonl("gmgn_bsc_kol_rank_x_verified.jsonl"):
        binding = row.get("x_binding") or {}
        if binding.get("verdict") != "PASS":
            continue
        high = (row.get("frequency_screen") or {}).get("verdict") == "REJECT"
        output[str(binding["stable_user_id"])].append({
            "source": "gmgn_7d_rank", "wallet": row["wallet"],
            "transactions_7d": row["transactions_7d"], "buys_7d": row["buys_7d"],
            "provider_tags": row["rank_tags"], "provider_high_frequency": high,
        })
    return {key: tuple(value) for key, value in output.items()}


def _catalog_role(actor) -> XAccountRole | None:
    if actor is None:
        return None
    if actor.tier in {ActorTier.GLOBAL_AGENDA, ActorTier.ECOSYSTEM_AUTHORITY}:
        return XAccountRole.CATALYST
    if actor.tier is ActorTier.PROPAGATION_KOL:
        return XAccountRole.KOL_CANDIDATE
    if actor.tier is ActorTier.DOMAIN_EXPERT:
        return XAccountRole.RESEARCH
    return None


def _summary(rows, reviews) -> dict[str, object]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["reviewed_role"] or "unreviewed")] += 1
    return {
        "schema": "debot4.x_account_candidate_summary.v1",
        "generated_at": datetime.now(UTC), "accounts": len(rows),
        "pre_peak_exact_ca_accounts": sum(row["has_pre_peak_exact_ca_post"] for row in rows),
        "wallet_bound_accounts": sum(bool(row["wallet_bindings"]) for row in rows),
        "role_counts": dict(sorted(counts.items())), "manual_role_reviews": len(reviews),
        "warning": "Queue membership is not KOL qualification or an instruction to trade.",
    }


def _joined_x_markets() -> tuple[dict, ...]:
    return (
        *_jsonl("bsc_market_x_joins.jsonl"),
        *_optional_jsonl("x_account_identity_market_joins.jsonl"),
        *_optional_jsonl("x_wallet_identity_market_joins.jsonl"),
        *_optional_jsonl("chinese_x_market_joins.jsonl"),
    )


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


def _optional_jsonl(name: str) -> tuple[dict, ...]:
    path = ROOT / name
    return _jsonl(name) if path.exists() else ()


def _json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
