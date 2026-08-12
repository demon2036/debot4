from __future__ import annotations

from decimal import Decimal

from debot4.v6.golden_dogs.gmgn_public import GmgnTaggedTrade, GmgnTradePage
from debot4.v6.golden_dogs.gmgn_trade_history import fetch_kol_trades_in_window
from debot4.v6.golden_dogs.models import EvidenceReceipt


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
RECEIPT = EvidenceReceipt("gmgn", "https://gmgn.ai/evidence", 1, "0" * 64)


def trade(at: int, suffix: str) -> GmgnTaggedTrade:
    return GmgnTaggedTrade(
        WALLET, CA, "buy", at, Decimal("1"), Decimal("1"), Decimal("1"),
        "0x" + suffix * 64, "KOL", "kol_x", ("kol",),
    )


class Client:
    def __init__(self) -> None:
        self.cursors = []

    def fetch_kol_trades(self, chain, token, *, cursor=None):
        self.cursors.append(cursor)
        if cursor is None:
            return GmgnTradePage((trade(210, "1"), trade(190, "2")), "next", RECEIPT)
        return GmgnTradePage((trade(110, "3"), trade(90, "4")), "older", RECEIPT)


class BurnOnlyBoundaryClient:
    def fetch_kol_trades(self, chain, token, *, cursor=None):
        return GmgnTradePage((), "older", RECEIPT, oldest_row_at=90)


def test_trade_pagination_crosses_window_start_before_claiming_complete() -> None:
    client = Client()
    result = fetch_kol_trades_in_window(client, CA, 100, 200)
    assert [item.timestamp for item in result.trades] == [110, 190]
    assert result.coverage_complete is True
    assert result.stop_reason == "crossed_window_start"
    assert client.cursors == [None, "next"]


def test_page_limit_is_explicitly_incomplete() -> None:
    result = fetch_kol_trades_in_window(Client(), CA, 1, 200, max_pages=1)
    assert result.coverage_complete is False
    assert result.stop_reason == "page_limit"


def test_ignored_event_can_prove_history_crossed_window_start() -> None:
    result = fetch_kol_trades_in_window(BurnOnlyBoundaryClient(), CA, 100, 200)
    assert result.trades == ()
    assert result.coverage_complete is True
    assert result.stop_reason == "crossed_window_start"
