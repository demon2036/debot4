from __future__ import annotations

import json

import httpx
import pytest

from debot4.v6.golden_dogs.bsc_rpc import VerifiedTokenSwap
from debot4.v6.golden_dogs.gmgn_kol_adapter import provider_buy_from_gmgn
from debot4.v6.golden_dogs.gmgn_public import PublicGmgnClient, PublicGmgnError
from debot4.v6.golden_dogs.models import EvidenceReceipt


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
TX = "0x" + "c" * 64


def test_gmgn_kol_trade_retains_wallet_tx_time_handle_and_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["tag"] == "kol"
        return httpx.Response(200, json={
            "code": 0,
            "data": {
                "history": [{
                    "maker": WALLET,
                    "token_address": CA,
                    "event": "buy",
                    "timestamp": 100,
                    "base_amount": "500",
                    "amount_usd": "12.5",
                    "price_usd": "0.025",
                    "tx_hash": TX,
                    "maker_name": "KOL Name",
                    "maker_twitter_username": "@exact_handle",
                    "maker_tags": ["kol", "wash_trader"],
                }],
                "next": "",
            },
        }, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://gmgn.ai") as raw:
        page = PublicGmgnClient(client=raw).fetch_kol_trades("bsc", CA)
    trade = page.trades[0]
    assert trade.wallet == WALLET
    assert trade.transaction_hash == TX
    assert trade.timestamp == 100
    assert trade.x_handle == "exact_handle"
    assert "wash_trader" in trade.tags
    assert page.receipt.kind == "gmgn_public_json"


def test_gmgn_trade_page_rejects_non_object_rows_instead_of_hiding_them() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"code": 0, "data": {"history": [None], "next": ""}},
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        with pytest.raises(PublicGmgnError, match="invalid schema"):
            PublicGmgnClient(client=raw).fetch_kol_trades("bsc", CA)


def test_gmgn_trade_page_ignores_non_trade_events_but_keeps_page_time() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "code": 0,
            "data": {"history": [{
                "maker": WALLET, "token_address": CA, "event": "burn",
                "timestamp": 90, "base_amount": "500", "amount_usd": "",
                "price_usd": "0", "tx_hash": TX, "maker_tags": ["kol"],
            }], "next": "older"},
        }, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        page = PublicGmgnClient(client=raw).fetch_kol_trades("bsc", CA)
    assert page.trades == ()
    assert page.oldest_row_at == 90


def test_gmgn_risk_snapshot_keeps_manipulation_inputs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert json.loads(request.content) == {"chain": "bsc", "addresses": [CA]}
        return httpx.Response(200, json={
            "code": 0,
            "data": [{
                "creator_address": WALLET,
                "top_10_holder_rate": "0.8359",
                "dev_team_hold_rate": "0",
                "creator_hold_rate": "0.01",
                "rug": False,
                "rug_ratio": "0.02",
                "creator_stat": {
                    "from_address": "0x" + "d" * 40,
                    "fund_from": "0x" + "e" * 40,
                    "fund_tx_hash": "0x" + "f" * 64,
                    "transfer_ts": 90,
                },
                "security": {"is_honeypot": False},
            }],
        }, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://gmgn.ai") as raw:
        risk = PublicGmgnClient(client=raw).fetch_risk("bsc", CA)
    assert str(risk.top_ten_holder_rate) == "0.8359"
    assert str(risk.creator_hold_rate) == "0.01"
    assert risk.rug is False
    assert str(risk.rug_ratio) == "0.02"
    assert risk.creator_fund_from == "0x" + "e" * 40
    assert risk.creator_fund_tx_hash == "0x" + "f" * 64
    assert risk.security["is_honeypot"] is False


def test_gmgn_buy_only_maps_after_matching_rpc_verification() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "code": 0,
            "data": {"history": [{
                "maker": WALLET, "token_address": CA, "event": "buy",
                "timestamp": 100, "base_amount": "500", "amount_usd": "12.5",
                "price_usd": "0.025", "tx_hash": TX, "maker_name": "Name",
                "maker_twitter_username": "handle", "maker_tags": ["kol", "gmgn"],
            }], "next": ""},
        }, request=request)

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="https://gmgn.ai") as raw:
        trade = PublicGmgnClient(client=raw).fetch_kol_trades("bsc", CA).trades[0]
    receipt = EvidenceReceipt("rpc", "https://bsc.example", 1, "0" * 64)
    verified = VerifiedTokenSwap(TX, WALLET, CA, 1, 100, 500, WALLET, 1, receipt)
    evidence = provider_buy_from_gmgn(
        trade, verified, provider_url=f"https://gmgn.ai/bsc/token/{CA}",
    )
    assert evidence.provider == "gmgn"
    assert evidence.trades[0].swap_verified is True
    assert evidence.trades[0].provider_alias == "handle"
    assert evidence.trades[0].risk_tags == ("gmgn", "kol")
