from __future__ import annotations

from decimal import Decimal
import pytest

from debot4.v6.golden_dogs.gmgn_market_history import (
    fetch_market_trades_in_window,
    trade_evidence_window_end,
)
from debot4.v6.golden_dogs.gmgn_market_trades import (
    GmgnMarketTrade,
    GmgnMarketTradePage,
)
from debot4.v6.golden_dogs.models import EvidenceReceipt


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
RECEIPT = EvidenceReceipt("gmgn", "https://gmgn.ai/evidence", 1, "0" * 64)


def trade(at: int, digit: str) -> GmgnMarketTrade:
    return GmgnMarketTrade(
        WALLET, CA, "buy", at, Decimal("1"), Decimal("1"), Decimal("1"),
        "0x" + digit * 64, "", None, ("smart_degen",), (), (),
    )


class Client:
    def __init__(self) -> None:
        self.calls = []

    def fetch_page(self, chain, token, *, end_at=None, cursor=None):
        self.calls.append((end_at, cursor))
        if cursor is None:
            return GmgnMarketTradePage(
                (trade(210, "1"), trade(190, "2")), "older", RECEIPT, 190,
            )
        return GmgnMarketTradePage(
            (trade(110, "3"), trade(90, "4")), "last", RECEIPT, 90,
        )


def test_history_anchors_at_end_then_crosses_start() -> None:
    client = Client()
    result = fetch_market_trades_in_window(client, CA, 100, 200)
    assert [item.timestamp for item in result.trades] == [110, 190]
    assert result.coverage_complete is True
    assert result.stop_reason == "crossed_window_start"
    assert client.calls == [(199, None), (None, "older")]


def test_history_page_limit_is_explicitly_incomplete() -> None:
    result = fetch_market_trades_in_window(Client(), CA, 100, 200, max_pages=1)
    assert result.coverage_complete is False
    assert result.stop_reason == "page_limit"


def test_history_rejects_unbounded_page_delay() -> None:
    with pytest.raises(ValueError, match="bounds"):
        fetch_market_trades_in_window(
            Client(), CA, 100, 200, page_delay_seconds=6,
        )


def test_trade_window_stays_open_through_delayed_breakout_candle() -> None:
    assert trade_evidence_window_end(
        motion_crossing_before=1_000,
        breakout_crossing_end_exclusive=3_000,
        wave_end_exclusive=4_000,
    ) == 3_060


def test_trade_window_uses_wave_end_when_breakout_is_missing() -> None:
    assert trade_evidence_window_end(
        motion_crossing_before=1_000,
        breakout_crossing_end_exclusive=None,
        wave_end_exclusive=4_000,
    ) == 4_000
