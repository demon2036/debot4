"""Immutable BSC zero-transfer evidence and launchpad-CA location rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..identity import utc_datetime
from .mint_location import BSC_LOG_SOURCE, MintLocation


TRANSFER_TOPIC = (
    "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
)
ZERO_TOPIC = "0x" + "0" * 64
KNOWN_LAUNCHPAD_TOKEN_SUFFIXES = ("4444", "7777", "8888", "ffff")


@dataclass(frozen=True, slots=True)
class BscMintBlock:
    number: int
    block_hash: str
    parent_hash: str
    timestamp: datetime
    zero_transfers: tuple[BscZeroTransferLog, ...] = ()


@dataclass(frozen=True, slots=True)
class BscZeroTransferLog:
    token_address: str
    transaction_hash: str
    block_number: int
    block_hash: str
    transaction_index: int
    log_index: int
    data: str


def locate_launchpad_mint_logs(
    block: BscMintBlock,
    logs: tuple[BscZeroTransferLog, ...],
    *,
    observed_at: datetime,
) -> tuple[MintLocation, ...]:
    """Locate raw Exact CAs from the mint invariant, independent of entry route.

    The source adapter has already requested ERC-20 Transfer logs whose sender is
    the zero address.  This rule deliberately claims only that a matching token
    emitted a successful canonical mint log; it does not authorize research or a
    trade and does not infer which narrative owns the token.
    """

    observed = utc_datetime(observed_at)
    found: dict[tuple[str, str], MintLocation] = {}
    for item in logs:
        if (
            item.block_number != block.number
            or item.block_hash != block.block_hash
        ):
            raise ValueError("BSC mint log does not belong to its block")
        if not item.token_address.endswith(KNOWN_LAUNCHPAD_TOKEN_SUFFIXES):
            continue
        if _quantity(item.data) <= 0:
            continue
        key = (item.transaction_hash, item.token_address)
        found[key] = MintLocation(
            exact_ca=item.token_address,
            source=BSC_LOG_SOURCE,
            observed_at=observed,
            created_at=block.timestamp,
            transaction_hash=item.transaction_hash,
            block_number=block.number,
            block_hash=block.block_hash,
            transaction_index=item.transaction_index,
        )
    return tuple(found[key] for key in sorted(found))


def _quantity(value: str) -> int:
    try:
        result = int(value, 16)
    except (TypeError, ValueError):
        return 0
    return max(0, result)
