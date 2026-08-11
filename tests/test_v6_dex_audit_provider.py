from __future__ import annotations

from collections.abc import Iterable

from debot4.v6.dex_audit.models import HttpAttempt, JsonResponse
from debot4.v6.dex_audit.providers import CMC_URL, GECKO_URL, fetch_bsc_gainers


def attempt(source: str, url: str) -> HttpAttempt:
    return HttpAttempt(
        source=source,
        method="POST" if source.startswith("coin") else "GET",
        url=url,
        request_json=None,
        started_at_us=1,
        completed_at_us=2,
        latency_ms=1,
        http_status=200,
        response_bytes=100,
        success=True,
        failure_reason=None,
    )


class FakeClient:
    def __init__(self, responses: Iterable[JsonResponse]) -> None:
        self.responses = iter(responses)
        self.calls: list[dict[str, object]] = []

    def request_json(self, **kwargs: object) -> JsonResponse:
        self.calls.append(kwargs)
        return next(self.responses)


def cmc_item(number: int, change: float, *, liquidity: int = 30_000) -> dict:
    return {
        "n": f"Token {number}",
        "sym": f"T{number}",
        "addr": f"0x{number:040x}",
        "pid": 14,
        "liqUsd": str(liquidity),
        "mcap": str(number * 100_000),
        "p": "0.001",
        "sts": [
            {
                "tp": "1h",
                "pc": change,
                "vu": str(number * 1_000),
                "txs": str(number),
            }
        ],
    }


def test_cmc_board_is_filtered_deduplicated_and_locally_sorted() -> None:
    items = [cmc_item(number, float(number)) for number in range(1, 26)]
    items.reverse()
    items.insert(3, cmc_item(99, 999.0, liquidity=10))
    items.insert(7, cmc_item(25, 1_000.0))
    payload = {"data": {"leaderboardList": items}}
    client = FakeClient([JsonResponse(payload, attempt("coinmarketcap_datahub", CMC_URL))])

    board = fetch_bsc_gainers(client, as_of_us=100)

    assert board.success and board.ranking_exact
    assert board.as_of_us == 2
    assert board.source == "coinmarketcap_datahub"
    assert len(board.rows) == 20
    assert [row.h1_change_pct for row in board.rows[:3]] == [1000, 24, 23]
    assert len({row.token_address for row in board.rows}) == 20
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request["url"] == CMC_URL
    assert request["method"] == "POST"
    assert request["body"]["sortBy"] == "priceChange1h"
    assert request["body"]["platformIds"] == "14"
    assert request["body"]["filter"] == {"minLiquidity": 25000.0}


def test_gecko_fallback_is_explicitly_not_a_global_ranking() -> None:
    cmc = JsonResponse(
        {"data": {"leaderboardList": []}},
        attempt("coinmarketcap_datahub", CMC_URL),
    )
    tokens = []
    pools = []
    for number, change in ((1, "2.5"), (2, "9.5"), (3, "4.5")):
        token = f"0x{number:040x}"
        tokens.append(
            {
                "type": "token",
                "id": f"bsc_{token}",
                "attributes": {"address": token, "symbol": f"T{number}"},
            }
        )
        pools.append(
            {
                "id": f"bsc_0x{number + 100:040x}",
                "attributes": {
                    "name": f"T{number} / WBNB",
                    "reserve_in_usd": "50000",
                    "price_change_percentage": {"h1": change},
                    "volume_usd": {"h1": "1000"},
                    "transactions": {"h1": {"buys": 4, "sells": 2}},
                },
                "relationships": {"base_token": {"data": {"id": f"bsc_{token}"}}},
            }
        )
    gecko = JsonResponse(
        {"data": pools, "included": tokens}, attempt("geckoterminal", GECKO_URL)
    )
    client = FakeClient([cmc, gecko])

    board = fetch_bsc_gainers(client, as_of_us=100)

    assert board.success and not board.ranking_exact
    assert board.as_of_us == 2
    assert board.source == "geckoterminal"
    assert [str(row.h1_change_pct) for row in board.rows] == ["9.5", "4.5", "2.5"]
    assert all(row.pair_address for row in board.rows)
    assert "not global" in (board.failure_reason or "")
    assert len(board.attempts) == 2
