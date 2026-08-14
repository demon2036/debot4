"""Bounded time-anchored collection of unfiltered GMGN token trades."""

from __future__ import annotations

from dataclasses import dataclass
import time

from .gmgn_market_trades import GmgnMarketTrade, PublicGmgnMarketTradeClient
from .models import EvidenceReceipt, normalize_evm_address


@dataclass(frozen=True, slots=True)
class GmgnMarketTradeHistory:
    trades: tuple[GmgnMarketTrade, ...]
    receipts: tuple[EvidenceReceipt, ...]
    coverage_complete: bool
    stop_reason: str


def trade_evidence_window_end(
    *,
    motion_crossing_before: int,
    breakout_crossing_end_exclusive: int | None,
    wave_end_exclusive: int,
    motion_tail_seconds: int = 120,
    breakout_tail_seconds: int = 60,
) -> int:
    """Keep the trade scan open through both motion and breakout evidence."""

    if (
        motion_crossing_before <= 0
        or wave_end_exclusive <= motion_crossing_before
        or motion_tail_seconds < 0
        or breakout_tail_seconds < 0
        or (
            breakout_crossing_end_exclusive is not None
            and breakout_crossing_end_exclusive <= 0
        )
    ):
        raise ValueError("invalid trade-evidence window bounds")
    breakout_end = (
        breakout_crossing_end_exclusive + breakout_tail_seconds
        if breakout_crossing_end_exclusive is not None
        else wave_end_exclusive
    )
    return max(motion_crossing_before + motion_tail_seconds, breakout_end)


def fetch_market_trades_in_window(
    client: PublicGmgnMarketTradeClient,
    token: str,
    window_start: int,
    window_end_exclusive: int,
    *,
    max_pages: int = 200,
    page_delay_seconds: float = 0,
) -> GmgnMarketTradeHistory:
    """Anchor at the requested end and page backward through the full window."""

    token = normalize_evm_address(token)
    if (
        not 0 < window_start < window_end_exclusive
        or not 1 <= max_pages <= 500
        or not 0 <= page_delay_seconds <= 5
    ):
        raise ValueError("invalid GMGN market-history bounds")
    rows: dict[tuple[str, str, str], GmgnMarketTrade] = {}
    receipts: list[EvidenceReceipt] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()
    complete, reason = False, "page_limit"
    for page_number in range(max_pages):
        page = client.fetch_page(
            "bsc", token,
            end_at=window_end_exclusive - 1 if page_number == 0 else None,
            cursor=cursor,
        )
        receipts.append(page.receipt)
        for trade in page.trades:
            if window_start <= trade.timestamp < window_end_exclusive:
                key = (trade.transaction_hash, trade.event, trade.wallet)
                rows[key] = trade
        if not page.next_cursor:
            complete, reason = True, "provider_history_exhausted"
            break
        if page.oldest_row_at is not None and page.oldest_row_at < window_start:
            complete, reason = True, "crossed_window_start"
            break
        if page.next_cursor in seen_cursors:
            reason = "cursor_loop"
            break
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor
        if page_delay_seconds:
            time.sleep(page_delay_seconds)
    ordered = tuple(sorted(
        rows.values(),
        key=lambda trade: (
            trade.timestamp,
            trade.provider_sequence is None,
            trade.provider_sequence or 0,
            trade.transaction_hash,
            trade.event,
            trade.wallet,
        ),
    ))
    return GmgnMarketTradeHistory(ordered, tuple(receipts), complete, reason)
