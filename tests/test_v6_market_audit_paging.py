from decimal import Decimal
from types import SimpleNamespace

import pytest

from debot4.v6.golden_dogs.market_audit import fetch_window_bars
from debot4.v6.golden_dogs.models import Candle, TokenSeed


def seed() -> TokenSeed:
    return TokenSeed(
        chain="bsc", address="0x" + "1" * 40, name="x", symbol="x",
        launchpad="fourmeme", created_at=100, creator_address=None,
        rank_supply=None, current_kols=0, max_kols=0, social_urls=(),
        discovered_sources=(),
    )


class FakeClient:
    def __init__(self) -> None:
        self.ends: list[int] = []

    def fetch_market(self, _chain: str, _address: str, **query: int):
        end = query["end"]
        self.ends.append(end)
        earliest = end - 1_000
        candles = (
            Candle(
                earliest, Decimal("1"), Decimal("1"), Decimal("1"),
                Decimal("1"), Decimal("1"),
            ),
        )
        return SimpleNamespace(
            candles=candles, total_supply=Decimal("10"),
            receipt=SimpleNamespace(sha256=str(end)),
        )


def test_page_budget_can_expand_for_one_minute_week() -> None:
    client = FakeClient()
    result = fetch_window_bars(
        client, seed(), 100, 10_100, 60, max_pages=12,
    )

    assert result.coverage_complete
    assert len(client.ends) == 10
    assert client.ends[-1] == 1_100


def test_invalid_page_budget_fails_before_network() -> None:
    client = FakeClient()
    with pytest.raises(ValueError, match="page limit"):
        fetch_window_bars(client, seed(), 100, 200, 60, max_pages=0)
    assert client.ends == []
