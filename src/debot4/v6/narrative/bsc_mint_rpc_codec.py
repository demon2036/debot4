"""Strict JSON-RPC decoding for BSC block headers and zero-transfer logs."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import datetime, timezone
import re

from ..identity import bsc_address
from .chain_mint import (
    TRANSFER_TOPIC,
    ZERO_TOPIC,
    BscMintBlock,
    BscZeroTransferLog,
)


_HASH = re.compile(r"0x[0-9a-f]{64}")
_HEX = re.compile(r"0x[0-9a-f]*")
_QUANTITY = re.compile(r"0x(?:0|[1-9a-f][0-9a-f]*)")
_WORD = re.compile(r"0x[0-9a-f]{64}")


def mint_block_from_rpc(
    raw_block: object, raw_logs: object, expected_number: int,
) -> BscMintBlock:
    block = block_from_rpc(raw_block, expected_number)
    return replace(
        block,
        zero_transfers=zero_transfers_from_rpc(raw_logs, block),
    )


def block_from_rpc(raw: object, expected_number: int) -> BscMintBlock:
    if not isinstance(raw, Mapping):
        raise ValueError
    actual = rpc_quantity(raw.get("number"))
    transactions = raw.get("transactions")
    if (
        actual != expected_number
        or not isinstance(transactions, list)
        or len(transactions) > 10_000
    ):
        raise ValueError
    for transaction_hash in transactions:
        rpc_hash(transaction_hash)
    return BscMintBlock(
        actual,
        rpc_hash(raw.get("hash")),
        rpc_hash(raw.get("parentHash")),
        datetime.fromtimestamp(rpc_quantity(raw.get("timestamp")), timezone.utc),
    )


def zero_transfers_from_rpc(
    raw: object, block: BscMintBlock,
) -> tuple[BscZeroTransferLog, ...]:
    if not isinstance(raw, list) or len(raw) > 10_000:
        raise ValueError
    decoded = tuple(_zero_transfer(item, block) for item in raw)
    identities = tuple(identity for identity, _item in decoded)
    if len(set(identities)) != len(identities):
        raise ValueError
    return tuple(item for _identity, item in decoded if item is not None)


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


def _zero_transfer(
    raw: object, block: BscMintBlock,
) -> tuple[tuple[str, int], BscZeroTransferLog | None]:
    if not isinstance(raw, Mapping) or raw.get("removed") is not False:
        raise ValueError
    topics = raw.get("topics")
    if not isinstance(topics, list) or not 2 <= len(topics) <= 8:
        raise ValueError
    normalized = tuple(str(item).casefold() for item in topics)
    if (
        any(not _WORD.fullmatch(item) for item in normalized)
        or normalized[0] != TRANSFER_TOPIC
        or normalized[1] != ZERO_TOPIC
    ):
        raise ValueError
    token_address = bsc_address(raw.get("address"))
    transaction_hash = rpc_hash(raw.get("transactionHash"))
    block_number = rpc_quantity(raw.get("blockNumber"))
    block_hash = rpc_hash(raw.get("blockHash"))
    transaction_index = rpc_quantity(raw.get("transactionIndex"))
    log_index = rpc_quantity(raw.get("logIndex"))
    if block_number != block.number or block_hash != block.block_hash:
        raise ValueError
    data = str(raw.get("data") or "").casefold()
    if not _HEX.fullmatch(data) or len(data) % 2:
        raise ValueError
    identity = (transaction_hash, log_index)
    if len(normalized) != 3 or not _WORD.fullmatch(data):
        return identity, None
    return identity, BscZeroTransferLog(
        token_address=token_address,
        transaction_hash=transaction_hash,
        block_number=block_number,
        block_hash=block_hash,
        transaction_index=transaction_index,
        log_index=log_index,
        data=data,
    )
