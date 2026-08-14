from __future__ import annotations

import json

import httpx
import pytest

from debot4.v6.narrative.bsc_mint_rpc import (
    BscMintRpcClient,
    BscMintRpcError,
)
from debot4.v6.narrative.chain_mint import TRANSFER_TOPIC, ZERO_TOPIC


BLOCK_HASH = "0x" + "1" * 64
PARENT_HASH = "0x" + "2" * 64
TX = "0x" + "3" * 64
CA = "0x417bda357cce720467edc56ebc6bb4c9ea497777"


def _result(request_id: int, result: object) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _handler(request: httpx.Request) -> httpx.Response:
    calls = json.loads(request.content)
    rows = []
    for call in calls:
        method = call["method"]
        if method == "eth_blockNumber":
            value = "0xa"
        elif method == "eth_getBlockByNumber":
            value = {
                "number": "0xa", "hash": BLOCK_HASH,
                "parentHash": PARENT_HASH, "timestamp": "0x64",
                "transactions": [TX],
            }
        elif method == "eth_getLogs":
            assert call["params"] == [{
                "blockHash": BLOCK_HASH,
                "topics": [TRANSFER_TOPIC, ZERO_TOPIC],
            }]
            value = [{
                "address": CA,
                "topics": [TRANSFER_TOPIC, ZERO_TOPIC, "0x" + "4" * 64],
                "data": "0x" + "0" * 63 + "1",
                "transactionHash": TX, "blockNumber": "0xa",
                "blockHash": BLOCK_HASH, "transactionIndex": "0x7",
                "logIndex": "0x9", "removed": False,
            }]
        else:
            raise AssertionError(method)
        rows.append(_result(call["id"], value))
    return httpx.Response(200, json=list(reversed(rows)))


def test_rpc_adapter_parses_bounded_headers_and_zero_transfers() -> None:
    with httpx.Client(transport=httpx.MockTransport(_handler)) as http:
        rpc = BscMintRpcClient(("https://rpc.example",), client=http)

        assert rpc.latest_block_number() == 10
        block = rpc.fetch_block(10)
        (mint_log,) = rpc.fetch_zero_transfers(block)

    assert block.number == 10
    assert block.block_hash == BLOCK_HASH
    assert mint_log.token_address == CA
    assert mint_log.transaction_hash == TX
    assert mint_log.transaction_index == 7
    assert mint_log.log_index == 9


def test_rpc_fails_over_when_first_endpoint_omits_response_identity() -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(str(request.url.host))
        call = json.loads(request.content)[0]
        if request.url.host == "bad.example":
            return httpx.Response(200, json=[{"jsonrpc": "2.0", "result": "0xa"}])
        return httpx.Response(200, json=[_result(call["id"], "0xa")])

    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        rpc = BscMintRpcClient(
            ("https://bad.example", "https://good.example"), client=http
        )
        assert rpc.latest_block_number() == 10

    assert hosts == ["bad.example", "good.example"]


def test_rpc_rejects_credential_url_and_oversized_response() -> None:
    with pytest.raises(ValueError, match="credential-free HTTPS"):
        BscMintRpcClient(("https://user:secret@rpc.example",))

    def large(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b" " * 1_025)

    with httpx.Client(transport=httpx.MockTransport(large)) as http:
        rpc = BscMintRpcClient(
            ("https://rpc.example",), max_response_bytes=1_024, client=http
        )
        with pytest.raises(BscMintRpcError, match="all BSC mint RPC"):
            rpc.latest_block_number()


@pytest.mark.parametrize(
    "payload",
    [
        [{"jsonrpc": "2.0", "id": "1", "result": "0xa"}],
        [{"jsonrpc": "2.0", "id": 1, "result": "10"}],
        [{"jsonrpc": "2.0", "id": 1, "result": "0x00"}],
    ],
)
def test_rpc_rejects_noncanonical_response_identity_and_quantities(
    payload: object,
) -> None:
    def malformed(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    with httpx.Client(transport=httpx.MockTransport(malformed)) as http:
        rpc = BscMintRpcClient(("https://rpc.example",), client=http)
        with pytest.raises(BscMintRpcError, match="all BSC mint RPC"):
            rpc.latest_block_number()
