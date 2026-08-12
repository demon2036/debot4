#!/usr/bin/env python3
"""Audit reviewed KOL CAs and current-cap Robinhood coverage gaps."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import json
from pathlib import Path

from debot4.v6.golden_dogs.blockscout_public import RobinhoodBlockscoutClient
from debot4.v6.golden_dogs.market_audit import MarketAuditResult, audit_markets
from debot4.v6.golden_dogs.debot_detail import parse_detail_seed
from debot4.v6.golden_dogs.debot_public import PublicDeBotClient
from debot4.v6.golden_dogs.kol_cases import KOL_TOKEN_CASES, UNRESOLVED_KOL_CLAIMS
from debot4.v6.golden_dogs.kol_evidence import KOL_WALLET_ATTRIBUTIONS
from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.token_index import collect_above_current_cap
from debot4.v6.golden_dogs.research_scope import windows_for_chain


ROOT = Path(__file__).resolve().parent
CURRENT_CAP_FLOOR = Decimal("1000000")
STABLE_OR_EXTERNAL_SYMBOLS = {
    "1INCH", "AAPL", "AMD", "AMZN", "APE", "DEGEN", "FLAY", "GOOGL", "GME",
    "GRID", "KARMA", "NPC", "NVDA", "SFI", "SNDK", "SPCX", "SPY", "SYRUPUSDG",
    "TSLA", "USDE", "USDG", "USDUC", "USO", "VIRTUAL", "WETH",
}


def debot_factory() -> PublicDeBotClient:
    return PublicDeBotClient(timeout_seconds=40, attempts=3)


def main() -> None:
    with RobinhoodBlockscoutClient(timeout_seconds=40) as blockscout:
        index = collect_above_current_cap(blockscout, CURRENT_CAP_FLOOR)
    write_jsonl(ROOT / "robinhood_current_cap_index.jsonl", index.rows)

    reviewed_addresses = {case.address for case in KOL_TOKEN_CASES}
    ranked_addresses = _load_ranked_addresses()
    gap_rows = tuple(
        row for row in index.rows
        if row.symbol.upper() not in STABLE_OR_EXTERNAL_SYMBOLS
        and row.address not in reviewed_addresses
        and row.address not in ranked_addresses
    )
    seeds = []
    detail_receipts = []
    detail_errors: list[tuple[str, str, str]] = []
    targets = tuple((case.chain, case.address) for case in KOL_TOKEN_CASES) + tuple(
        ("robinhood", row.address) for row in gap_rows
    )
    with debot_factory() as client:
        for chain, address in dict.fromkeys(targets):
            try:
                page = client.fetch_token_detail(chain, address)
                seeds.append(parse_detail_seed(page))
                detail_receipts.append(page.receipt)
            except Exception as exc:
                detail_errors.append((chain, address, type(exc).__name__))

    audit = _audit_with_retries(seeds)
    by_key = {(item.chain, item.address): item for item in audit.observations}
    case_rows = []
    for case in KOL_TOKEN_CASES:
        observation = by_key.get((case.chain, case.address))
        case_rows.append({
            **asdict(case),
            "tweet_url": case.tweet_url,
            "timing": _timing(case, observation),
            "meets_peak_threshold": (
                observation.meets_peak_threshold if observation is not None else None
            ),
            "observation": observation,
        })
    write_jsonl(ROOT / "kol_case_observations.jsonl", case_rows)
    write_jsonl(ROOT / "kol_wallet_evidence.jsonl", KOL_WALLET_ATTRIBUTIONS)
    write_jsonl(
        ROOT / "robinhood_exact_ca_observations.jsonl",
        (
            item for item in audit.observations
            if item.chain == "robinhood" and item.address in {row.address for row in gap_rows}
        ),
    )
    write_json(ROOT / "exact_audit_coverage.json", {
        "schema": "debot4.golden_dog_exact_audit.v1",
        "blockscout_current_cap_floor_usd": CURRENT_CAP_FLOOR,
        "blockscout_rows_above_floor": len(index.rows),
        "blockscout_pages": len(index.receipts),
        "blockscout_threshold_traversal_complete": index.complete,
        "blockscout_stopped_below_usd": index.stopped_below_usd,
        "ranked_universe_addresses": len(ranked_addresses),
        "excluded_known_external_or_stock_symbols": sorted(STABLE_OR_EXTERNAL_SYMBOLS),
        "exact_ca_targets": len(tuple(dict.fromkeys(targets))),
        "detail_receipts": len(detail_receipts),
        "detail_errors": detail_errors,
        "market_observations": len(audit.observations),
        "market_errors": audit.errors,
        "unresolved_kol_claims": UNRESOLVED_KOL_CLAIMS,
        "scope_warning": (
            "Blockscout supplement is complete only for tokens currently above $1M in its "
            "cap-sorted index; it cannot recover tokens that peaked above $1M then fell below it"
        ),
    })
    print(
        f"index={len(index.rows)} gap_targets={len(gap_rows)} "
        f"observed={len(audit.observations)} errors={len(audit.errors) + len(detail_errors)}"
    )


def _timing(case, observation) -> str:
    if observation is None or observation.peak_at is None:
        return "unresolved"
    if (
        case.published_peak_fdv_usd is not None
        and observation.approx_peak_fdv_usd is not None
        and Decimal(case.published_peak_fdv_usd) >= observation.approx_peak_fdv_usd * Decimal("0.9")
    ):
        return "retrospective_peak_claim"
    return "post_peak" if case.posted_at > observation.peak_at else "pre_peak"


def _load_ranked_addresses() -> set[str]:
    path = ROOT / "robinhood_universe.jsonl"
    return {
        str(json.loads(line)["address"]).casefold()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }


def _audit_with_retries(seeds) -> MarketAuditResult:
    """Retry only failed CAs; successful immutable observations are retained."""

    pending = {(seed.chain, seed.address): seed for seed in seeds}
    observations = {}
    last_errors = ()
    for workers in (6, 3, 1):
        if not pending:
            break
        windows = {
            chain: windows_for_chain(chain)
            for chain in {seed.chain for seed in pending.values()}
        }
        result = audit_markets(
            debot_factory, pending.values(), windows, workers=workers,
        )
        for item in result.observations:
            observations[(item.chain, item.address)] = item
            pending.pop((item.chain, item.address), None)
        last_errors = result.errors
    errors = tuple(
        item for item in last_errors
        if (item[0], item[1]) in pending
    )
    return MarketAuditResult(
        tuple(sorted(observations.values(), key=lambda item: (item.chain, item.created_at, item.address))),
        errors,
    )


if __name__ == "__main__":
    main()
