from __future__ import annotations

import httpx

from debot4.v6.golden_dogs.gmgn_wallet_public import PublicGmgnWalletClient


WALLET = "0x" + "a" * 40
FUNDER = "0x" + "b" * 40


def test_wallet_profile_unions_trade_independent_risk_tags() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/walletNew/" in request.url.path:
            data = {
                "name": "Public Name", "twitter_username": "@exact_x",
                "twitter_bind": True, "twitter_fans_num": 1234,
                "tags": ["kol", "gmgn"], "risk": {},
            }
        else:
            data = {
                "name": "Stat Name", "twitter_username": "exact_x",
                "tags": ["kol", "wash_trader"], "risk": {"suspected": True},
                "fund_from": FUNDER, "fund_tx_hash": "0x" + "c" * 64,
            }
        return httpx.Response(200, json={"code": 0, "data": data}, request=request)

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        profile = PublicGmgnWalletClient(client=raw).fetch_profile("bsc", WALLET)
    assert profile.wallet == WALLET
    assert profile.x_handle == "exact_x"
    assert profile.public_x_handle == "exact_x"
    assert profile.stat_x_handle == "exact_x"
    assert profile.x_bound is True
    assert profile.x_fans == 1234
    assert profile.tags == ("gmgn", "kol", "wash_trader")
    assert profile.fund_from == FUNDER
    assert len(profile.receipts) == 2


def test_conflicting_provider_handles_are_not_silently_bound() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        handle = "first_x" if "/walletNew/" in request.url.path else "other_x"
        return httpx.Response(
            200,
            json={"code": 0, "data": {
                "twitter_username": handle, "twitter_bind": True, "tags": [],
            }},
            request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        profile = PublicGmgnWalletClient(client=raw).fetch_profile("bsc", WALLET)
    assert profile.x_handle is None
    assert profile.public_x_handle == "first_x"
    assert profile.stat_x_handle == "other_x"


def test_rank_snapshot_keeps_frozen_winrate_denominator() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["orderby"] == "winrate_7d"
        row = {
            "wallet_address": WALLET, "name": "Ranked", "twitter_username": "x_rank",
            "tags": ["kol"], "winrate_7d": "0.75", "txs_7d": 120,
            "buy_7d": 80, "sell_7d": 40, "realized_profit_7d": "123.45",
        }
        return httpx.Response(
            200, json={"code": 0, "data": {"rank": [row]}}, request=request,
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gmgn.ai",
    ) as raw:
        snapshot = PublicGmgnWalletClient(client=raw).fetch_kol_rank()
    assert snapshot.ordered_by == "winrate_7d"
    assert snapshot.rows[0].transactions_7d == 120
    assert str(snapshot.rows[0].winrate_7d) == "0.75"
