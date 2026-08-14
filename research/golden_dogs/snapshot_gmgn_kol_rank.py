#!/usr/bin/env python3
"""Freeze GMGN's public KOL wallet rank as an unqualified audit pool."""

from pathlib import Path

from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient
from debot4.v6.golden_dogs.serialization import write_json
from debot4.v6.golden_dogs.wallet_risk import has_manipulative_wallet_tag


ROOT = Path(__file__).resolve().parent


def main() -> None:
    with PublicGmgnWalletClient(timeout_seconds=40) as client:
        snapshot = client.fetch_kol_rank("bsc")
    risk_screened = tuple(
        row for row in snapshot.rows if not has_manipulative_wallet_tag(row.tags)
    )
    x_attributed = tuple(row for row in risk_screened if row.x_handle)
    write_json(ROOT / "gmgn_bsc_kol_rank_7d.json", {
        "schema": "debot4.gmgn_bsc_kol_rank.v1",
        "fetched_at": snapshot.fetched_at,
        "provider_ordered_by": snapshot.ordered_by,
        "provider_rows": len(snapshot.rows),
        "risk_screened_rows": len(risk_screened),
        "x_attributed_rows": len(x_attributed),
        "rows": risk_screened,
        "receipt": snapshot.receipt,
        "warning": (
            "Unqualified audit pool only. Provider win rate and profit are not selection "
            "criteria. High-frequency indiscriminate wallets must be excluded after complete "
            "activity-history reconstruction. X attribution is optional and independently "
            "verified when present; anonymous selective wallets remain eligible."
        ),
    })
    print(
        f"provider_rows={len(snapshot.rows)} risk_screened={len(risk_screened)} "
        f"x_attributed={len(x_attributed)}"
    )


if __name__ == "__main__":
    main()
