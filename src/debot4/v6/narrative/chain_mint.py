"""Immutable BSC receipt inputs and reviewed launchpad mint rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..identity import bsc_address, utc_datetime
from .mint_location import BSC_FACTORY_SOURCE, MintLocation


FLAP_FACTORY = "0x880a2c2d5009c4f50e8c3b2220361e19805c6666"
TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
ZERO_TOPIC = "0x" + "0" * 64
FLAP_TOKEN_SUFFIX = "7777"


@dataclass(frozen=True, slots=True)
class BscMintTransaction:
    transaction_hash: str
    to_address: str | None
    transaction_index: int


@dataclass(frozen=True, slots=True)
class BscMintBlock:
    number: int
    block_hash: str
    parent_hash: str
    timestamp: datetime
    transactions: tuple[BscMintTransaction, ...]


@dataclass(frozen=True, slots=True)
class BscMintLog:
    address: str
    topics: tuple[str, ...]
    data: str
    transaction_hash: str


@dataclass(frozen=True, slots=True)
class BscMintReceipt:
    transaction_hash: str
    to_address: str | None
    succeeded: bool
    block_number: int
    block_hash: str
    transaction_index: int
    logs: tuple[BscMintLog, ...]


def is_verified_factory_transaction(transaction: BscMintTransaction) -> bool:
    """Cheap block-level filter; the receipt rule remains authoritative."""

    return transaction.to_address == FLAP_FACTORY


def locate_verified_flap_mints(
    block: BscMintBlock,
    transaction: BscMintTransaction,
    receipt: BscMintReceipt,
    *,
    observed_at: datetime,
) -> tuple[MintLocation, ...]:
    """Extract exact token emitters only from a successful reviewed factory call."""

    if not is_verified_factory_transaction(transaction):
        return ()
    if (
        not receipt.succeeded
        or receipt.to_address != FLAP_FACTORY
        or receipt.transaction_hash != transaction.transaction_hash
        or receipt.block_number != block.number
        or receipt.block_hash != block.block_hash
        or receipt.transaction_index != transaction.transaction_index
    ):
        return ()
    exact_cas: set[str] = set()
    for log in receipt.logs:
        if (
            log.transaction_hash != transaction.transaction_hash
            or len(log.topics) < 3
            or log.topics[0] != TRANSFER_TOPIC
            or log.topics[1] != ZERO_TOPIC
            or not log.address.endswith(FLAP_TOKEN_SUFFIX)
            or _quantity(log.data) <= 0
        ):
            continue
        exact_cas.add(bsc_address(log.address))
    observed = utc_datetime(observed_at)
    return tuple(
        MintLocation(
            exact_ca=exact_ca,
            source=BSC_FACTORY_SOURCE,
            observed_at=observed,
            created_at=block.timestamp,
            launchpad="flap",
            transaction_hash=transaction.transaction_hash,
            block_number=block.number,
            block_hash=block.block_hash,
            transaction_index=transaction.transaction_index,
            factory_address=FLAP_FACTORY,
        )
        for exact_ca in sorted(exact_cas)
    )


def _quantity(value: str) -> int:
    try:
        result = int(value, 16)
    except (TypeError, ValueError):
        return 0
    return max(0, result)
