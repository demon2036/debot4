from __future__ import annotations

import base64
import httpx
import pytest

from debot4.v6.golden_dogs.gmgn_market_trades import (
    GmgnMarketTradeError,
    PublicGmgnMarketTradeClient,
)


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
TX = "0x" + "c" * 64


def test_unfiltered_trade_retains_smart_tags_and_uses_end_anchor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "tag" not in request.url.params
        assert request.url.params["to"] == "200"
        return httpx.Response(200, json={"code": 0, "data": {
            "history": [{
                "maker": WALLET, "token_address": CA, "event": "buy",
                "timestamp": 190, "base_amount": "500", "amount_usd": "12.5",
                "price_usd": "0.025", "tx_hash": TX, "maker_name": "Wallet",
                "maker_twitter_username": "@actor",
                "id": base64.b64encode(b"123456789").decode(),
                "maker_tags": ["smart_degen", "app_smart_money"],
                "maker_token_tags": ["first_buy"], "maker_event_tags": ["signal"],
            }], "next": "older",
        }}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        page = PublicGmgnMarketTradeClient(client=raw).fetch_page(
            "bsc", CA, end_at=200,
        )
    trade = page.trades[0]
    assert trade.wallet_tags == ("app_smart_money", "smart_degen")
    assert trade.token_tags == ("first_buy",)
    assert trade.event_tags == ("signal",)
    assert trade.provider_sequence == 123456789
    assert trade.x_handle == "actor"
    assert page.oldest_row_at == 190


def test_launch_event_allows_empty_market_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {
            "history": [{
                "maker": WALLET, "token_address": CA, "event": "launch",
                "timestamp": 100, "base_amount": "", "amount_usd": "",
                "price_usd": "0", "tx_hash": TX, "maker_tags": ["fresh_wallet"],
                "maker_token_tags": ["creator"], "maker_event_tags": [],
            }], "next": "",
        }}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        trade = PublicGmgnMarketTradeClient(client=raw).fetch_page("bsc", CA).trades[0]
    assert trade.event == "launch"
    assert trade.amount_usd is None
    assert trade.price_usd == 0
    assert trade.token_tags == ("creator",)


def test_buy_rejects_missing_positive_market_values() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {
            "history": [{
                "maker": WALLET, "token_address": CA, "event": "buy",
                "timestamp": 100, "base_amount": "", "amount_usd": "1",
                "price_usd": "1", "tx_hash": TX, "maker_tags": [],
                "maker_token_tags": [], "maker_event_tags": [],
            }], "next": "",
        }}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        with pytest.raises(GmgnMarketTradeError, match="must be positive"):
            PublicGmgnMarketTradeClient(client=raw).fetch_page("bsc", CA)


def test_provider_zero_value_sell_is_retained_as_unpriced_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 0, "data": {
            "history": [{
                "maker": WALLET, "token_address": CA, "event": "sell",
                "timestamp": 100, "base_amount": "", "amount_usd": "",
                "price_usd": "0", "tx_hash": TX, "maker_tags": [],
                "maker_token_tags": [], "maker_event_tags": [],
            }], "next": "",
        }}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        trade = PublicGmgnMarketTradeClient(client=raw).fetch_page("bsc", CA).trades[0]
    assert trade.event == "sell"
    assert trade.price_usd is None
