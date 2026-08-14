from __future__ import annotations

import json

import httpx

from debot4.v6.golden_dogs.bsc_rpc import PublicBscRpcClient, TRANSFER_TOPIC


CA = "0x" + "a" * 40
WALLET = "0x" + "b" * 40
ROUTER = "0x" + "c" * 40
PAIR = "0x" + "d" * 40
TX = "0x" + "e" * 64


def test_rpc_verifies_sender_success_and_token_received() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        method = body["method"]
        result = {
            "eth_getTransactionByHash": {
                "hash": TX, "from": WALLET, "to": ROUTER,
                "blockNumber": "0x10", "transactionIndex": "0x3", "value": "0x64",
            },
            "eth_getTransactionReceipt": {
                "status": "0x1",
                "logs": [{
                    "address": CA,
                    "topics": [
                        TRANSFER_TOPIC,
                        "0x" + "0" * 24 + PAIR[2:],
                        "0x" + "0" * 24 + WALLET[2:],
                    ],
                    "data": "0x2a",
                }],
            },
            "eth_getBlockByNumber": {"timestamp": "0x20"},
        }[method]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as raw:
        result = PublicBscRpcClient(client=raw).verify_token_buy(TX, WALLET, CA)
    assert result.wallet == WALLET
    assert result.token_received_raw == 42
    assert result.block_timestamp == 32
    assert result.transaction_index == 3
    assert result.native_value_wei == 100
    assert result.receipt.kind == "bsc_public_rpc_bundle"


def test_rpc_fetches_generic_transaction_block_position() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        method = json.loads(request.content)["method"]
        result = {
            "eth_getTransactionByHash": {
                "hash": TX, "blockNumber": "0x10", "transactionIndex": "0x7",
            },
            "eth_getBlockByNumber": {"timestamp": "0x20"},
        }[method]
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(handler)) as raw:
        result = PublicBscRpcClient(client=raw).fetch_transaction_position(TX)
    assert (result.block_number, result.transaction_index, result.block_timestamp) == (16, 7, 32)
    assert result.receipt.kind == "bsc_public_rpc_position"
