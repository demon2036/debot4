#!/usr/bin/env python3
"""Join verified X exact-CA posts to independently audited KOL-buy tokens."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    qualifications = {
        str(row["address"]).casefold(): row
        for row in _jsonl("bsc_gmgn_qualification.jsonl")
    }
    wallet_owners = _wallet_owners()
    rows = []
    seen: set[tuple[str, str]] = set()
    for join in _joins():
        x, market = join["x"], join["market"]
        address = str(market["address"]).casefold()
        key = (str(x["status_url"]), address)
        if key in seen or address not in qualifications:
            continue
        seen.add(key)
        rows.append(_intersection(join, qualifications[address], wallet_owners))
    rows.sort(key=lambda row: (
        row["x"]["published_at"], row["address"], row["x"]["status_url"],
    ))
    write_jsonl(ROOT / "x_kol_buy_intersections.jsonl", rows)
    write_json(ROOT / "x_kol_buy_intersection_summary.json", _summary(rows))


def _intersection(join: dict, qualification: dict, owners: dict[str, str]) -> dict:
    x, market = join["x"], join["market"]
    clean_buys = qualification.get("clean_buys") or []
    stable_id = str(x["stable_user_id"])
    own_buys = [buy for buy in clean_buys
                if owners.get(str(buy["wallet"]).casefold()) == stable_id]
    post_at = int(datetime.fromisoformat(
        str(x["published_at"]).replace("Z", "+00:00"),
    ).timestamp())
    return {
        "schema": "debot4.x_kol_buy_intersection.v1",
        "address": str(market["address"]).casefold(),
        "token": {"name": qualification["name"], "symbol": qualification["symbol"]},
        "market": {
            "window_start": market["window_start"],
            "window_end_exclusive": market["window_end_exclusive"],
            "total_supply": market["total_supply"],
            "supply_source": market["supply_source"],
            "approx_peak_fdv_usd": market["approx_peak_fdv_usd"],
            "peak_at": market["peak_at"],
        },
        "x": {
            "stable_user_id": stable_id, "handle": x["handle"],
            "status_url": x["status_url"], "published_at": x["published_at"],
            "text": x["text"], "status_payload_sha256": x["status_payload_sha256"],
            "profile_payload_sha256": x["profile_payload_sha256"],
        },
        "x_post_timing": join["timing"],
        "kol_buy_audit": {
            "qualification_outcome": qualification["outcome"],
            "qualification_reasons": qualification["reasons"],
            "rpc_verified_clean_buy_count": len(clean_buys),
            "rpc_verified_clean_buy_wallet_count": len({
                str(buy["wallet"]).casefold() for buy in clean_buys
            }),
            "pre_peak_clean_buy_count": sum(
                buy.get("before_market_peak") is True for buy in clean_buys
            ),
            "earliest_clean_buy": _buy(min(
                clean_buys, key=lambda buy: int(buy["bought_at"]), default=None,
            )),
            "x_author_bound_wallet_buy_count": len(own_buys),
            "x_author_bound_wallet_buy_sample": [_buy(buy) for buy in own_buys[:3]],
            "x_author_wallet_timing": dict(sorted(Counter(
                _author_buy_timing(int(buy["bought_at"]), post_at, int(market["peak_at"]))
                for buy in own_buys
            ).items())),
        },
        "warning": (
            "The X author and provider-tagged buyer are different evidence axes. "
            "Only x_author_bound_wallet_buy_count proves an exact author-wallet overlap."
        ),
    }


def _author_buy_timing(buy_at: int, post_at: int, peak_at: int) -> str:
    if buy_at < post_at:
        return "buy_before_post"
    if buy_at < peak_at:
        return "buy_after_post_before_peak"
    return "buy_after_peak"


def _buy(buy: dict | None) -> dict | None:
    if buy is None:
        return None
    return {
        "wallet": str(buy["wallet"]).casefold(),
        "transaction_hash": buy["transaction_hash"],
        "bought_at": buy["bought_at"], "amount_usd": buy.get("amount_usd"),
        "before_market_peak": buy.get("before_market_peak"),
        "provider_name": buy.get("provider_name"),
        "provider_x_handle": buy.get("provider_x_handle"),
    }


def _wallet_owners() -> dict[str, str]:
    owners = {}
    for row in _jsonl("bsc_audit_wallet_x_verified.jsonl"):
        binding = row.get("x_binding") or {}
        if binding.get("verdict") == "PASS":
            owners[str(row["wallet"]).casefold()] = str(binding["stable_user_id"])
    return owners


def _summary(rows: list[dict]) -> dict[str, object]:
    clean = [row for row in rows
             if row["kol_buy_audit"]["rpc_verified_clean_buy_count"] > 0]
    own = [row for row in rows
           if row["kol_buy_audit"]["x_author_bound_wallet_buy_count"] > 0]
    return {
        "schema": "debot4.x_kol_buy_intersection_summary.v1",
        "generated_at": datetime.now(UTC),
        "verified_status_ca_pairs": len(rows),
        "unique_x_accounts": len({row["x"]["stable_user_id"] for row in rows}),
        "unique_audited_tokens": len({row["address"] for row in rows}),
        "post_timing": dict(sorted(Counter(row["x_post_timing"] for row in rows).items())),
        "pairs_on_tokens_with_rpc_clean_buy": len(clean),
        "tokens_with_rpc_clean_buy": len({row["address"] for row in clean}),
        "pre_peak_post_pairs_on_rpc_clean_buy_tokens": sum(
            row["x_post_timing"] == "pre_peak" for row in clean
        ),
        "exact_x_author_wallet_buy_pairs": len(own),
        "qualification_outcomes": dict(sorted(Counter(
            row["kol_buy_audit"]["qualification_outcome"] for row in rows
        ).items())),
        "warning": (
            "Token-level intersection is not proof that the posting account bought, "
            "called first, caused the move, or passed manipulation checks."
        ),
    }


def _joins() -> tuple[dict, ...]:
    return (
        *_jsonl("bsc_market_x_joins.jsonl"),
        *_optional_jsonl("x_account_identity_market_joins.jsonl"),
        *_optional_jsonl("x_wallet_identity_market_joins.jsonl"),
        *_optional_jsonl("chinese_x_market_joins.jsonl"),
        *_optional_jsonl("tintin_x_market_joins.jsonl"),
    )


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


def _optional_jsonl(name: str) -> tuple[dict, ...]:
    return _jsonl(name) if (ROOT / name).exists() else ()


if __name__ == "__main__":
    main()
