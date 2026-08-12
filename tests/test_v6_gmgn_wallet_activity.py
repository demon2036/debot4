from __future__ import annotations

import httpx

from debot4.v6.golden_dogs.gmgn_wallet_activity import (
    PublicGmgnWalletActivityClient,
)


WALLET = "0x" + "a" * 40
TOKEN = "0x" + "b" * 40


def row(
    timestamp: int, digit: str, *, event: str = "buy", token: str = TOKEN,
) -> dict[str, object]:
    return {
        "wallet": WALLET, "chain": "bsc", "tx_hash": "0x" + digit * 64,
        "timestamp": timestamp, "event_type": event, "token": {"address": token},
    }


def test_wallet_activity_pages_until_period_start_is_crossed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "cursor" not in request.url.params:
            data = {"activities": [row(250, "1")], "next": "second"}
        else:
            data = {"activities": [row(150, "2"), row(90, "3")], "next": "third"}
        return httpx.Response(200, json={"code": 0, "data": data}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        client = PublicGmgnWalletActivityClient(client=raw)
        history = client.fetch_history(WALLET, 100, 300)
    assert history.coverage_complete is True
    assert history.stop_reason == "crossed_period_start"
    assert [item.timestamp for item in history.activities] == [150, 250]
    assert len(history.receipts) == 2


def test_wallet_activity_page_limit_is_incomplete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"code": 0, "data": {
                "activities": [row(250, "4")], "next": "always",
            }}, request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        history = PublicGmgnWalletActivityClient(client=raw).fetch_history(
            WALLET, 100, 300, max_pages=1,
        )
    assert history.coverage_complete is False
    assert history.stop_reason == "page_limit"


def test_wallet_activity_preserves_burns_and_multiple_token_legs() -> None:
    other = "0x" + "c" * 40

    def handler(request: httpx.Request) -> httpx.Response:
        transaction = "5"
        return httpx.Response(
            200, json={"code": 0, "data": {"activities": [
                row(200, transaction, event="burn"),
                row(200, transaction, token=other),
                row(200, transaction),
            ], "next": ""}}, request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        history = PublicGmgnWalletActivityClient(client=raw).fetch_history(
            WALLET, 100, 300,
        )
    assert len(history.activities) == 3
    assert {item.event for item in history.activities} == {"burn", "buy"}
    assert {item.token_address for item in history.activities} == {TOKEN, other}
