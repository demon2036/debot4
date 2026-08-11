"""Small failover JSON-RPC client with fixed-block batch calls."""

from __future__ import annotations

from datetime import datetime, timezone
from threading import Lock
from typing import Any, Iterable, Sequence

import httpx

from ..domain import ChainHead
from .evm import block_tag


UTC = timezone.utc


class RpcError(RuntimeError):
    """All configured BSC RPC endpoints failed or returned invalid data."""


class BscRpc:
    def __init__(self, endpoints: Iterable[str], *, timeout_seconds: float = 3.0) -> None:
        self.endpoints = tuple(str(item) for item in endpoints)
        if not self.endpoints:
            raise ValueError("at least one RPC endpoint is required")
        self._client = httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            limits=httpx.Limits(max_connections=8, max_keepalive_connections=4),
            headers={"Content-Type": "application/json", "User-Agent": "debot4-v6/1.0"},
        )
        self._next_endpoint = 0
        self._request_id = 0
        self._lock = Lock()

    def close(self) -> None:
        self._client.close()

    def head(self) -> ChainHead:
        result = self.call("eth_getBlockByNumber", ["latest", False])
        if not isinstance(result, dict):
            raise RpcError("BSC head response is invalid")
        try:
            number = int(str(result["number"]), 16)
            block_hash = str(result["hash"]).lower()
            parent_hash = str(result["parentHash"]).lower()
            timestamp = datetime.fromtimestamp(int(str(result["timestamp"]), 16), UTC)
        except (KeyError, TypeError, ValueError, OSError) as exc:
            raise RpcError("BSC head fields are invalid") from exc
        hashes = (block_hash, parent_hash)
        if any(len(value) != 66 or not value.startswith("0x") for value in hashes):
            raise RpcError("BSC block hash is invalid")
        return ChainHead(number, block_hash, parent_hash, timestamp, datetime.now(UTC))

    def eth_calls(
        self, calls: Sequence[dict[str, str]], *, block_number: int
    ) -> tuple[str, ...]:
        requests = [("eth_call", [item, block_tag(block_number)]) for item in calls]
        result = self.batch(requests)
        if any(not isinstance(item, str) for item in result):
            raise RpcError("eth_call batch returned invalid results")
        return tuple(str(item) for item in result)

    def call(self, method: str, params: Sequence[object]) -> Any:
        return self.batch(((method, params),))[0]

    def batch(self, requests: Sequence[tuple[str, Sequence[object]]]) -> tuple[Any, ...]:
        if not requests:
            return ()
        with self._lock:
            ids = [self._new_id() for _ in requests]
            body = [
                {"jsonrpc": "2.0", "id": request_id, "method": method, "params": list(params)}
                for request_id, (method, params) in zip(ids, requests)
            ]
            errors = []
            for offset in range(len(self.endpoints)):
                index = (self._next_endpoint + offset) % len(self.endpoints)
                endpoint = self.endpoints[index]
                try:
                    response = self._client.post(endpoint, json=body)
                    response.raise_for_status()
                    payload = response.json()
                    values = _batch_values(payload, ids)
                except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
                    errors.append(type(exc).__name__)
                    continue
                self._next_endpoint = index
                return values
        raise RpcError("all BSC RPC endpoints failed: " + ",".join(errors))

    def _new_id(self) -> int:
        self._request_id += 1
        return self._request_id


def _batch_values(payload: object, ids: Sequence[int]) -> tuple[Any, ...]:
    rows = payload if isinstance(payload, list) else [payload]
    indexed = {}
    for row in rows:
        if not isinstance(row, dict) or "id" not in row:
            raise ValueError("RPC batch row is invalid")
        if row.get("error") is not None:
            raise ValueError("RPC method returned an error")
        indexed[int(row["id"])] = row.get("result")
    if any(request_id not in indexed for request_id in ids):
        raise ValueError("RPC batch response is incomplete")
    return tuple(indexed[request_id] for request_id in ids)
