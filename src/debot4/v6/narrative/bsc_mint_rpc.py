"""Bounded public BSC JSON-RPC adapter for the mint-location fast path."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
import json
from threading import Lock
from typing import Any
from urllib.parse import urlsplit

import httpx

from .chain_mint import (
    TRANSFER_TOPIC,
    ZERO_TOPIC,
    BscMintBlock,
    BscZeroTransferLog,
)
from .bsc_mint_rpc_codec import (
    batch_values,
    block_from_rpc,
    rpc_quantity,
    zero_transfers_from_rpc,
)


class BscMintRpcError(RuntimeError):
    """All RPC failures collapse to a credential-free operational error."""


class BscMintRpcClient:
    def __init__(
        self,
        endpoints: Iterable[str],
        *,
        timeout_seconds: float = 3.0,
        max_response_bytes: int = 2_000_000,
        client: httpx.Client | None = None,
    ) -> None:
        self.endpoints = tuple(_endpoint(item) for item in endpoints)
        if not self.endpoints:
            raise ValueError("at least one BSC RPC endpoint is required")
        if not 0 < float(timeout_seconds) <= 30:
            raise ValueError("BSC mint RPC timeout must be in (0, 30]")
        if not 1_024 <= int(max_response_bytes) <= 8 * 1_024 * 1_024:
            raise ValueError("BSC mint RPC byte limit is invalid")
        self.max_bytes = int(max_response_bytes)
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=float(timeout_seconds),
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
            headers={"Accept": "application/json", "User-Agent": "debot4-mint/1"},
        )
        self._lock = Lock()
        self._request_id = 0
        self._next_endpoint = 0

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def latest_block_number(self) -> int:
        return self._batch(
            (("eth_blockNumber", ()),),
            validator=lambda rows: (rpc_quantity(rows[0]),),
        )[0]

    def fetch_block(self, number: int) -> BscMintBlock:
        if isinstance(number, bool) or number < 0:
            raise ValueError("BSC block number must be non-negative")
        return self._batch(
            (("eth_getBlockByNumber", (hex(number), False)),),
            validator=lambda rows: (block_from_rpc(rows[0], number),),
        )[0]

    def fetch_zero_transfers(
        self, block: BscMintBlock,
    ) -> tuple[BscZeroTransferLog, ...]:
        return self._batch(
            (("eth_getLogs", ({
                "blockHash": block.block_hash,
                "topics": [TRANSFER_TOPIC, ZERO_TOPIC],
            },)),),
            validator=lambda rows: (zero_transfers_from_rpc(rows[0], block),),
        )[0]

    def _batch(
        self,
        requests: Sequence[tuple[str, Sequence[object]]],
        *,
        validator: Callable[[tuple[Any, ...]], tuple[Any, ...]] | None = None,
    ) -> tuple[Any, ...]:
        if not requests:
            return ()
        with self._lock:
            ids = tuple(self._new_id() for _ in requests)
            body = [
                {"jsonrpc": "2.0", "id": request_id, "method": method,
                 "params": list(params)}
                for request_id, (method, params) in zip(ids, requests)
            ]
            for offset in range(len(self.endpoints)):
                index = (self._next_endpoint + offset) % len(self.endpoints)
                try:
                    payload = self._post(self.endpoints[index], body)
                    values = batch_values(payload, ids)
                    if validator is not None:
                        values = validator(values)
                except (
                    httpx.HTTPError, OSError, OverflowError, TypeError,
                    UnicodeError, ValueError,
                ):
                    continue
                self._next_endpoint = index
                return values
        raise BscMintRpcError("all BSC mint RPC endpoints failed")

    def _post(self, endpoint: str, body: list[dict[str, object]]) -> object:
        chunks: list[bytes] = []
        size = 0
        with self._client.stream("POST", endpoint, json=body) as response:
            response.raise_for_status()
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > self.max_bytes:
                    raise ValueError("BSC RPC response exceeded byte limit")
                chunks.append(chunk)
        return json.loads(b"".join(chunks).decode("utf-8"))

    def _new_id(self) -> int:
        self._request_id += 1
        return self._request_id


def _endpoint(value: object) -> str:
    result = str(value).strip()
    parsed = urlsplit(result)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username or parsed.password or parsed.query or parsed.fragment
    ):
        raise ValueError("BSC RPC endpoint must be credential-free HTTPS")
    return result
