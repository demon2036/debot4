#!/usr/bin/env python3
"""Join stable X identities, bound wallets, exact CAs, and verified BSC swaps."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.x_wallet_timeline import classify_wallet_post_timing
from debot4.v6.golden_dogs.x_wallet_claim import corroborated_claim_from_mapping


ROOT = Path(__file__).resolve().parent
UTC = timezone.utc


def main() -> None:
    joins = _unique_pre_peak_joins(_joined_x_markets())
    wallets = _wallets()
    audits = {str(row["address"]).casefold(): row
              for row in _jsonl("bsc_gmgn_kol_audit_v2.jsonl")}
    rows = tuple(_timeline(row, wallets, audits) for row in joins
                 if str(row["x"]["stable_user_id"]) in wallets)
    rows = tuple(sorted(rows, key=lambda row: (
        str(row["handle"]), str(row["address"]), str(row["status_url"]),
    )))
    write_jsonl(ROOT / "x_wallet_post_timelines.jsonl", rows)
    write_json(ROOT / "x_wallet_post_timeline_summary.json", _summary(rows))


def _wallets() -> dict[str, tuple[dict[str, object], ...]]:
    output: dict[str, list[dict[str, object]]] = {}
    for name in (
        "bsc_audit_wallet_x_verified.jsonl",
        "gmgn_bsc_kol_rank_x_verified.jsonl",
    ):
        for row in _jsonl(name):
            binding = row.get("x_binding") or {}
            if binding.get("verdict") != "PASS":
                continue
            stable_id = str(binding["stable_user_id"])
            evidence = {
                "wallet": str(row["wallet"]).casefold(),
                "source": name,
                "provider_high_frequency": (
                    (row.get("frequency_screen") or {}).get("verdict") == "REJECT"
                ),
            }
            if evidence not in output.setdefault(stable_id, []):
                output[stable_id].append(evidence)
    for row in _json("x_public_wallet_claims.json"):
        claim = corroborated_claim_from_mapping(row)
        if claim is None:
            continue
        evidence = {
            "wallet": claim.wallet,
            "source": "x_public_wallet_claims.json",
            "provider_high_frequency": False,
        }
        if evidence not in output.setdefault(claim.stable_user_id, []):
            output[claim.stable_user_id].append(evidence)
    return {key: tuple(value) for key, value in output.items()}


def _timeline(
    join: dict, wallets: dict[str, tuple[dict[str, object], ...]], audits: dict,
) -> dict[str, object]:
    x, market = join["x"], join["market"]
    address, stable_id = str(market["address"]).casefold(), str(x["stable_user_id"])
    post_at = int(datetime.fromisoformat(
        str(x["published_at"]).replace("Z", "+00:00"),
    ).timestamp())
    peak_at = int(market["peak_at"])
    audit = audits.get(address)
    buys = []
    for binding in wallets[stable_id]:
        wallet = str(binding["wallet"])
        for item in (audit or {}).get("verified_kol_buys", []):
            trade = item.get("provider_trade") or {}
            if str(trade.get("wallet") or "").casefold() != wallet:
                continue
            buy_at = int(trade["timestamp"])
            buys.append({
                **binding, "bought_at": buy_at,
                "timing": classify_wallet_post_timing(
                    buy_at=buy_at, post_at=post_at, peak_at=peak_at,
                ),
                "transaction_hash": trade.get("transaction_hash"),
                "amount_usd": trade.get("amount_usd"),
                "rpc_verified": item.get("chain_verified") is True,
                "clean_in_window": item.get("clean_in_window") is True,
            })
    return {
        "schema": "debot4.x_wallet_post_timeline.v1",
        "stable_user_id": stable_id, "handle": x["handle"],
        "status_url": x["status_url"], "address": address,
        "post_at": x["published_at"], "peak_at": peak_at,
        "audit_scope": "present" if audit else "absent_max_kols_zero_or_not_audited",
        "bound_wallets": wallets[stable_id], "exact_ca_wallet_buys": buys,
        "wallet_is_optional_secondary_evidence": True,
    }


def _summary(rows: tuple[dict[str, object], ...]) -> dict[str, object]:
    unique = {(row["stable_user_id"], row["address"], row["status_url"]) for row in rows}
    matches = [buy for row in rows for buy in row["exact_ca_wallet_buys"]]
    return {
        "schema": "debot4.x_wallet_post_timeline_summary.v1",
        "generated_at": datetime.now(UTC), "identity_ca_post_intersections": len(unique),
        "exact_ca_wallet_buy_count": len(matches),
        "timing": dict(sorted(Counter(str(item["timing"]) for item in matches).items())),
        "warning": (
            "A wallet/X provider binding is optional attribution evidence. No exact-CA "
            "buy means no wallet claim; it does not erase the independently verified X post."
        ),
    }


def _unique_pre_peak_joins(rows: tuple[dict, ...]) -> tuple[dict, ...]:
    output = {}
    for row in rows:
        if row.get("timing") != "pre_peak":
            continue
        key = (
            str(row["x"]["status_url"]),
            str(row["market"]["address"]).casefold(),
        )
        output[key] = row
    return tuple(output[key] for key in sorted(output))


def _joined_x_markets() -> tuple[dict, ...]:
    return (
        *_jsonl("bsc_market_x_joins.jsonl"),
        *_optional_jsonl("x_account_identity_market_joins.jsonl"),
        *_optional_jsonl("x_wallet_identity_market_joins.jsonl"),
        *_optional_jsonl("chinese_x_market_joins.jsonl"),
        *_optional_jsonl("chinese_profile_deep_x_market_joins.jsonl"),
        *_optional_jsonl("tintin_x_market_joins.jsonl"),
    )


def _jsonl(name: str) -> tuple[dict, ...]:
    return tuple(json.loads(line) for line in (ROOT / name).read_text(
        encoding="utf-8",
    ).splitlines() if line.strip())


def _optional_jsonl(name: str) -> tuple[dict, ...]:
    return _jsonl(name) if (ROOT / name).exists() else ()


def _json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
