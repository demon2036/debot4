"""Strict JSON-RPC decoding for BSC mint blocks and receipts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
import re
from typing import Any

from ..identity import bsc_address
from .chain_mint import (
    BscMintBlock,
    BscMintLog,
    BscMintReceipt,
    BscMintTransaction,
)


_HASH = re.compile(r"0x[0-9a-f]{64}")
_HEX = re.compile(r"0x[0-9a-f]*")
_QUANTITY = re.compile(r"0x(?:0|[1-9a-f][0-9a-f]*)")


def block_from_rpc(raw: object, expected_number: int) -> BscMintBlock:
    if not isinstance(raw, Mapping):
        raise ValueError
    actual = rpc_quantity(raw.get("number"))
    rows = raw.get("transactions")
    if actual != expected_number or not isinstance(rows, list) or len(rows) > 10_000:
        raise ValueError
    return BscMintBlock(
        actual,
        rpc_hash(raw.get("hash")),
        rpc_hash(raw.get("parentHash")),
        datetime.fromtimestamp(rpc_quantity(raw.get("timestamp")), timezone.utc),
        tuple(_transaction(item) for item in rows),
    )


def receipts_from_rpc(
    rows: tuple[Any, ...], expected_hashes: tuple[str, ...],
) -> tuple[BscMintReceipt, ...]:
    receipts = tuple(_receipt(item) for item in rows)
    if tuple(item.transaction_hash for item in receipts) != expected_hashes:
        raise ValueError
    return receipts


def batch_values(payload: object, ids: Sequence[int]) -> tuple[object, ...]:
    rows = payload if isinstance(payload, list) else [payload]
    indexed: dict[int, object] = {}
    for row in rows:
        if (
            not isinstance(row, Mapping)
            or row.get("error") is not None
            or "id" not in row
        ):
            raise ValueError
        response_id = row["id"]
        if isinstance(response_id, bool) or not isinstance(response_id, int):
            raise ValueError
        if response_id in indexed:
            raise ValueError
        indexed[response_id] = row.get("result")
    if any(request_id not in indexed for request_id in ids):
        raise ValueError
    return tuple(indexed[request_id] for request_id in ids)


def rpc_quantity(value: object) -> int:
    raw = str(value).casefold()
    if not _QUANTITY.fullmatch(raw):
        raise ValueError
    return int(raw, 16)


def rpc_hash(value: object) -> str:
    result = str(value or "").casefold()
    if not _HASH.fullmatch(result):
        raise ValueError
    return result


def _transaction(raw: object) -> BscMintTransaction:
    if not isinstance(raw, Mapping):
        raise ValueError
    to_raw = raw.get("to")
    return BscMintTransaction(
        rpc_hash(raw.get("hash")),
        None if to_raw is None else bsc_address(to_raw),
        rpc_quantity(raw.get("transactionIndex")),
    )


def _receipt(raw: object) -> BscMintReceipt:
    if not isinstance(raw, Mapping):
        raise ValueError
    status = rpc_quantity(raw.get("status"))
    rows = raw.get("logs")
    if status not in {0, 1} or not isinstance(rows, list) or len(rows) > 10_000:
        raise ValueError
    to_raw = raw.get("to")
    return BscMintReceipt(
        transaction_hash=rpc_hash(raw.get("transactionHash")),
        to_address=None if to_raw is None else bsc_address(to_raw),
        succeeded=status == 1,
        block_number=rpc_quantity(raw.get("blockNumber")),
        block_hash=rpc_hash(raw.get("blockHash")),
        transaction_index=rpc_quantity(raw.get("transactionIndex")),
        logs=tuple(_log(item) for item in rows),
    )


def _log(raw: object) -> BscMintLog:
    if not isinstance(raw, Mapping):
        raise ValueError
    topics = raw.get("topics")
    data = str(raw.get("data") or "").casefold()
    if (
        not isinstance(topics, list) or len(topics) > 8
        or not _HEX.fullmatch(data)
    ):
        raise ValueError
    normalized = tuple(str(item).casefold() for item in topics)
    if any(not _HASH.fullmatch(item) for item in normalized):
        raise ValueError
    return BscMintLog(
        bsc_address(raw.get("address")), normalized, data,
        rpc_hash(raw.get("transactionHash")),
    )
