#!/usr/bin/env python3
"""Join the fixed 13-contract wave replay to RPC-verified GMGN-tagged buys."""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from debot4.v6.golden_dogs.serialization import write_json, write_jsonl
from debot4.v6.golden_dogs.market_waves import wave_phase_bounds
from debot4.v6.golden_dogs.wave_chain import ChainBuy, summarize_chain_activity


ROOT = Path(__file__).resolve().parent
REPLAYS = ROOT / "bsc_week_wave_replays.jsonl"
AUDIT = ROOT / "bsc_gmgn_kol_audit_v2.jsonl"
QUALIFICATION = ROOT / "bsc_gmgn_qualification.jsonl"
def main() -> None:
    replays = _by_address(REPLAYS)
    audits = _by_address(AUDIT)
    qualifications = _by_address(QUALIFICATION)
    rows: list[dict[str, object]] = []
    for address, replay in replays.items():
        audit = audits.get(address)
        qualification = qualifications.get(address)
        if audit is None or qualification is None:
            raise RuntimeError(f"missing chain evidence for {address}")
        if not audit.get("gmgn_history_coverage_complete"):
            raise RuntimeError(f"incomplete GMGN history for {address}")
        clean_hashes = {
            str(item["transaction_hash"]).casefold()
            for item in qualification.get("clean_buys", ())
        }
        buys = _parse_buys(audit, clean_hashes)
        effective = [
            wave for wave in replay["completed_swings"] if wave["effective"]
        ]
        for wave_number, wave in enumerate(effective, 1):
            bounds = wave_phase_bounds(
                window_start=int(replay["window_start"]),
                window_end_exclusive=int(replay["window_end_exclusive"]),
                trough_at=int(wave["trough_at"]),
                peak_at=int(wave["peak_at"]),
                reset_at=int(wave["reset_at"]),
            )
            rows.append({
                "schema": "debot4.bsc_week_wave_chain_join.v1",
                "label": replay["label"],
                "address": address,
                "wave_number": wave_number,
                "wave": wave,
                "phase_semantics": {
                    "pre_trough": "30m immediately before trough-candle start",
                    "ascent": "trough-candle start through peak-candle end",
                    "decay": "after peak-candle end through reset-candle end",
                },
                "pre_trough": _activity(
                    buys, bounds.pre_trough_start, bounds.trough_start,
                ),
                "ascent": _activity(
                    buys, bounds.trough_start, bounds.peak_end_exclusive,
                ),
                "decay": _activity(
                    buys, bounds.peak_end_exclusive, bounds.reset_end_exclusive,
                ),
                "qualification_outcome": qualification["outcome"],
                "qualification_reasons": qualification["reasons"],
            })
    rows.sort(key=lambda row: (str(row["address"]), int(row["wave_number"])))
    write_jsonl(ROOT / "bsc_week_wave_chain_joins.jsonl", rows)
    write_json(ROOT / "bsc_week_wave_chain_join_summary.json", {
        "schema": "debot4.bsc_week_wave_chain_join_summary.v1",
        "wave_count": len(rows),
        "target_count": len({row["address"] for row in rows}),
        "source_sha256": {
            REPLAYS.name: _sha256(REPLAYS),
            AUDIT.name: _sha256(AUDIT),
            QUALIFICATION.name: _sha256(QUALIFICATION),
        },
        "rpc_verified_tagged_buys": sum(
            int(row[phase]["tagged_buy_count"])
            for row in rows for phase in ("pre_trough", "ascent", "decay")
        ),
        "warning": (
            "GMGN KOL tags are provider labels, not independently proven identities. "
            "Clean is the existing risk-filter subset; every target remains WAIT while "
            "shared-funding and wash/circular manipulation checks are incomplete."
        ),
    })
    print(f"joined {len(rows)} effective waves across {len(replays)} contracts")


def _parse_buys(row: dict[str, object], clean_hashes: set[str]) -> tuple[ChainBuy, ...]:
    parsed = []
    for item in row.get("verified_kol_buys", ()):  # type: ignore[union-attr]
        provider = item["provider_trade"]
        rpc = item["rpc_swap"]
        tx_hash = str(provider["transaction_hash"]).casefold()
        parsed.append(ChainBuy(
            timestamp=int(provider["timestamp"]),
            transaction_hash=tx_hash,
            wallet=str(provider["wallet"]).casefold(),
            amount_usd=Decimal(str(provider["amount_usd"])),
            x_handle=(str(provider["x_handle"]) if provider.get("x_handle") else None),
            tags=tuple(str(tag) for tag in provider.get("tags", ())),
            rpc_receipt_sha256=str(rpc["receipt"]["sha256"]),
            clean=tx_hash in clean_hashes,
        ))
    return tuple(parsed)


def _activity(buys: tuple[ChainBuy, ...], start: int, end: int) -> dict[str, object]:
    result = asdict(summarize_chain_activity(buys, start, end))
    return result


def _by_address(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        address = str(row["address"]).casefold()
        if address in rows:
            raise RuntimeError(f"duplicate address in {path.name}: {address}")
        rows[address] = row
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
