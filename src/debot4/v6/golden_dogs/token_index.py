"""Application traversal for a current market-cap-ordered Blockscout token index."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .blockscout_public import RobinhoodBlockscoutClient, TokenIndexRow
from .models import EvidenceReceipt


@dataclass(frozen=True, slots=True)
class TokenIndexResult:
    rows: tuple[TokenIndexRow, ...]
    receipts: tuple[EvidenceReceipt, ...]
    stopped_below_usd: Decimal | None
    complete: bool


def collect_above_current_cap(
    client: RobinhoodBlockscoutClient,
    minimum_usd: Decimal,
    *,
    max_pages: int = 100,
) -> TokenIndexResult:
    """Traverse until the cap-sorted index drops below the threshold."""

    if minimum_usd <= 0 or not 1 <= max_pages <= 1_000:
        raise ValueError("invalid token-index collection bounds")
    rows: list[TokenIndexRow] = []
    receipts: list[EvidenceReceipt] = []
    params = None
    stopped_below = None
    complete = False
    for _ in range(max_pages):
        page = client.fetch_token_page(params)
        receipts.append(page.receipt)
        for row in page.rows:
            cap = row.circulating_market_cap_usd
            if cap is None:
                continue
            if cap < minimum_usd:
                stopped_below = cap
                complete = True
                break
            rows.append(row)
        if complete or page.next_page_params is None:
            complete = True
            break
        params = page.next_page_params
    return TokenIndexResult(tuple(rows), tuple(receipts), stopped_below, complete)
