"""Read-only BSC JSON-RPC verification for exact KOL swap locators."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import time
from typing import Any, Mapping

import httpx

from .models import EvidenceReceipt, normalize_evm_address


RPC_URL = "https://bsc-dataseed.binance.org"
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
_TX_HASH = re.compile(r"0x[0-9a-f]{64}")


class BscRpcError(RuntimeError):
    """Sanitized BSC JSON-RPC transport or schema failure."""


@dataclass(frozen=True, slots=True)
class VerifiedTokenSwap:
    transaction_hash: str
    wallet: str
    token_address: str
    block_number: int
    transaction_index: int
    block_timestamp: int
    token_received_raw: int
    transaction_to: str
    native_value_wei: int
    receipt: EvidenceReceipt


@dataclass(frozen=True, slots=True)
class BscTransactionPosition:
    transaction_hash: str
    block_number: int
    transaction_index: int
    block_timestamp: int
    receipt: EvidenceReceipt


class PublicBscRpcClient:
    def __init__(self, *, timeout_seconds: float = 30, attempts: int = 3,
                 client: httpx.Client | None = None) -> None:
        if timeout_seconds <= 0 or not 1 <= attempts <= 5:
            raise ValueError("invalid BSC RPC client bounds")
        self.attempts = attempts
        self._owns_client = client is None
        self._client = client or httpx.Client(
            timeout=timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            headers={"Accept": "application/json", "User-Agent": "DeBot4EvidenceResearch/1.0"},
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "PublicBscRpcClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def verify_token_buy(self, tx_hash: str, wallet: str,
                         token: str) -> VerifiedTokenSwap:
        tx_hash = _transaction_hash(tx_hash)
        wallet = normalize_evm_address(wallet)
        token = normalize_evm_address(token)
        tx, tx_raw = self._call("eth_getTransactionByHash", [tx_hash])
        receipt, receipt_raw = self._call("eth_getTransactionReceipt", [tx_hash])
        if not isinstance(tx, Mapping) or not isinstance(receipt, Mapping):
            raise BscRpcError("BSC transaction is unavailable")
        if str(tx.get("hash") or "").casefold() != tx_hash:
            raise BscRpcError("BSC transaction hash mismatch")
        if normalize_evm_address(str(tx.get("from") or "")) != wallet:
            raise BscRpcError("BSC transaction sender does not match KOL wallet")
        if str(receipt.get("status") or "").casefold() != "0x1":
            raise BscRpcError("BSC transaction did not succeed")
        received = _received_token_amount(receipt.get("logs"), token, wallet)
        if received <= 0:
            raise BscRpcError("BSC transaction has no token transfer to KOL wallet")
        block_number = _hex_int(tx.get("blockNumber"))
        block, block_raw = self._call("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(block, Mapping):
            raise BscRpcError("BSC transaction block is unavailable")
        raw = tx_raw + receipt_raw + block_raw
        return VerifiedTokenSwap(
            transaction_hash=tx_hash,
            wallet=wallet,
            token_address=token,
            block_number=block_number,
            transaction_index=_hex_int(tx.get("transactionIndex")),
            block_timestamp=_hex_int(block.get("timestamp")),
            token_received_raw=received,
            transaction_to=normalize_evm_address(str(tx.get("to") or "")),
            native_value_wei=_hex_int(tx.get("value")),
            receipt=EvidenceReceipt(
                kind="bsc_public_rpc_bundle",
                url=RPC_URL,
                fetched_at=int(time.time()),
                sha256=hashlib.sha256(raw).hexdigest(),
            ),
        )

    def fetch_transaction_position(self, tx_hash: str) -> BscTransactionPosition:
        """Fetch immutable block position without asserting swap semantics."""

        tx_hash = _transaction_hash(tx_hash)
        tx, tx_raw = self._call("eth_getTransactionByHash", [tx_hash])
        if not isinstance(tx, Mapping):
            raise BscRpcError("BSC transaction is unavailable")
        if str(tx.get("hash") or "").casefold() != tx_hash:
            raise BscRpcError("BSC transaction hash mismatch")
        block_number = _hex_int(tx.get("blockNumber"))
        block, block_raw = self._call("eth_getBlockByNumber", [hex(block_number), False])
        if not isinstance(block, Mapping):
            raise BscRpcError("BSC transaction block is unavailable")
        raw = tx_raw + block_raw
        return BscTransactionPosition(
            transaction_hash=tx_hash,
            block_number=block_number,
            transaction_index=_hex_int(tx.get("transactionIndex")),
            block_timestamp=_hex_int(block.get("timestamp")),
            receipt=EvidenceReceipt(
                kind="bsc_public_rpc_position",
                url=RPC_URL,
                fetched_at=int(time.time()),
                sha256=hashlib.sha256(raw).hexdigest(),
            ),
        )

    def _call(self, method: str, params: list[object]) -> tuple[object, bytes]:
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
        last_error: Exception | None = None
        for attempt in range(self.attempts):
            try:
                response = self._client.post(RPC_URL, json=body)
                if response.status_code != 200:
                    raise BscRpcError(f"BSC RPC returned HTTP {response.status_code}")
                raw = response.content
                if len(raw) > 8_000_000:
                    raise BscRpcError("BSC RPC response exceeded byte limit")
                payload = response.json()
                if not isinstance(payload, Mapping) or payload.get("error") is not None:
                    raise BscRpcError("BSC RPC returned an error envelope")
                return payload.get("result"), raw
            except (httpx.HTTPError, json.JSONDecodeError, BscRpcError) as exc:
                last_error = exc
                if attempt + 1 < self.attempts:
                    time.sleep(0.25 * (2**attempt))
        raise BscRpcError("BSC RPC request failed") from last_error


def _received_token_amount(logs: object, token: str, wallet: str) -> int:
    if not isinstance(logs, list):
        raise BscRpcError("BSC receipt logs have invalid schema")
    total = 0
    for item in logs:
        if not isinstance(item, Mapping):
            continue
        topics = item.get("topics")
        if (str(item.get("address") or "").casefold() != token
                or not isinstance(topics, list) or len(topics) < 3
                or str(topics[0]).casefold() != TRANSFER_TOPIC):
            continue
        recipient = "0x" + str(topics[2]).casefold()[-40:]
        if recipient == wallet:
            total += _hex_int(item.get("data"))
    return total


def _hex_int(value: object) -> int:
    try:
        result = int(str(value), 16)
    except (TypeError, ValueError) as exc:
        raise BscRpcError("BSC RPC contains an invalid hex integer") from exc
    if result < 0:
        raise BscRpcError("BSC RPC contains a negative integer")
    return result


def _transaction_hash(value: str) -> str:
    result = value.strip().casefold()
    if not _TX_HASH.fullmatch(result):
        raise ValueError("invalid BSC transaction hash")
    return result
