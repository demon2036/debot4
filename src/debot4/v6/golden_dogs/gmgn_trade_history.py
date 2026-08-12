"""Bounded pagination of GMGN KOL trades for one audited market window."""

from __future__ import annotations

from dataclasses import dataclass

from .gmgn_public import GmgnTaggedTrade, PublicGmgnClient
from .models import EvidenceReceipt, normalize_evm_address


@dataclass(frozen=True, slots=True)
class GmgnWindowTrades:
    trades: tuple[GmgnTaggedTrade, ...]
    receipts: tuple[EvidenceReceipt, ...]
    coverage_complete: bool
    stop_reason: str


def fetch_kol_trades_in_window(
    client: PublicGmgnClient,
    token: str,
    window_start: int,
    window_end_exclusive: int,
    *,
    max_pages: int = 40,
) -> GmgnWindowTrades:
    """Page newest-to-oldest until the requested window is fully crossed."""

    token = normalize_evm_address(token)
    if not 0 < window_start < window_end_exclusive or not 1 <= max_pages <= 100:
        raise ValueError("invalid GMGN trade-history bounds")
    by_transaction: dict[str, GmgnTaggedTrade] = {}
    receipts: list[EvidenceReceipt] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    complete = False
    reason = "page_limit"
    for _ in range(max_pages):
        page = client.fetch_kol_trades("bsc", token, cursor=cursor)
        receipts.append(page.receipt)
        for trade in page.trades:
            if window_start <= trade.timestamp < window_end_exclusive:
                by_transaction[trade.transaction_hash] = trade
        if not page.next_cursor:
            complete, reason = True, "provider_history_exhausted"
            break
        oldest = page.oldest_row_at
        if oldest is None and page.trades:
            oldest = min(item.timestamp for item in page.trades)
        if oldest is not None and oldest < window_start:
            complete, reason = True, "crossed_window_start"
            break
        if page.next_cursor in seen_cursors:
            reason = "cursor_loop"
            break
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor
    return GmgnWindowTrades(
        tuple(sorted(by_transaction.values(), key=lambda item: item.timestamp)),
        tuple(receipts), complete, reason,
    )
