"""Low-latency application loop for reviewed BSC factory mint receipts."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
import math
from time import monotonic
from typing import Protocol

from ..identity import utc_datetime, utc_now
from .chain_mint import (
    BscMintBlock,
    BscMintReceipt,
    is_verified_factory_transaction,
    locate_verified_flap_mints,
)
from .chain_mint_state import ChainMintCheckpoint, ChainMintCheckpointStore
from .mint_location import MintLocation


DEFAULT_CHAIN_MINT_POLL_SECONDS = 0.25


class ChainMintRpc(Protocol):
    def latest_block_number(self) -> int: ...
    def fetch_block(self, number: int) -> BscMintBlock: ...
    def fetch_receipts(
        self, transaction_hashes: Sequence[str]
    ) -> tuple[BscMintReceipt, ...]: ...


class BscFactoryMintMonitor:
    """Checkpoint only after exact locations have reached durable storage."""

    def __init__(
        self,
        rpc: ChainMintRpc,
        checkpoints: ChainMintCheckpointStore,
        *,
        poll_seconds: float = DEFAULT_CHAIN_MINT_POLL_SECONDS,
        startup_lookback_blocks: int = 3,
        max_catchup_blocks: int = 64,
        timer: Callable[[], float] = monotonic,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not 0.1 <= float(poll_seconds) <= 2:
            raise ValueError("chain mint poll must be between 0.1 and 2 seconds")
        if (
            isinstance(startup_lookback_blocks, bool)
            or not 1 <= startup_lookback_blocks <= 16
        ):
            raise ValueError("chain mint startup lookback must be between 1 and 16")
        if (
            isinstance(max_catchup_blocks, bool)
            or not startup_lookback_blocks <= max_catchup_blocks <= 512
        ):
            raise ValueError("chain mint catchup bound is invalid")
        self.rpc = rpc
        self.checkpoints = checkpoints
        self.poll_seconds = float(poll_seconds)
        self.startup_lookback_blocks = startup_lookback_blocks
        self.max_catchup_blocks = max_catchup_blocks
        self.timer = timer
        self.clock = clock
        self._next_poll_at = 0.0
        self.last_head: int | None = None
        self.last_processed_block: int | None = None
        self.locations_persisted = 0
        self.skipped_stale_blocks = 0
        self.reorg_recoveries = 0

    def poll_once(
        self,
        accept: Callable[[tuple[MintLocation, ...]], object] | None = None,
    ) -> tuple[MintLocation, ...]:
        tick = float(self.timer())
        if not math.isfinite(tick):
            raise ValueError("chain mint timer must be finite")
        if tick < self._next_poll_at:
            return ()
        self._next_poll_at = tick + self.poll_seconds
        head = self.rpc.latest_block_number()
        self.last_head = head
        previous = self.checkpoints.load()
        numbers, compare_parent = self._block_numbers(head, previous)
        if not numbers:
            return ()
        blocks = self._fetch_sequence(numbers)
        if (
            compare_parent is not None
            and blocks[0].parent_hash != compare_parent.block_hash
        ):
            self.reorg_recoveries += 1
            start = max(0, head - self.startup_lookback_blocks + 1)
            blocks = self._fetch_sequence(tuple(range(start, head + 1)))
        found: list[MintLocation] = []
        prior_hash: str | None = None
        for block in blocks:
            if prior_hash is not None and block.parent_hash != prior_hash:
                raise RuntimeError("BSC mint block sequence is not contiguous")
            locations = self._locations(block)
            if locations and accept is not None:
                accept(locations)
            found.extend(locations)
            if accept is not None:
                self.checkpoints.save(
                    ChainMintCheckpoint(block.number, block.block_hash)
                )
                self.last_processed_block = block.number
                self.locations_persisted += len(locations)
            prior_hash = block.block_hash
        return tuple(found)

    def snapshot(self) -> dict[str, object]:
        return {
            "poll_seconds": self.poll_seconds,
            "last_head": self.last_head,
            "last_processed_block": self.last_processed_block,
            "locations_persisted": self.locations_persisted,
            "skipped_stale_blocks": self.skipped_stale_blocks,
            "reorg_recoveries": self.reorg_recoveries,
            "verified_factories": 1,
            "confirmation_depth": 0,
            "finality": "included_not_finalized",
            "authorizes_trade": False,
        }

    def _block_numbers(
        self, head: int, previous: ChainMintCheckpoint | None,
    ) -> tuple[tuple[int, ...], ChainMintCheckpoint | None]:
        if isinstance(head, bool) or head < 0:
            raise ValueError("BSC head must be a non-negative integer")
        if previous is None:
            start = max(0, head - self.startup_lookback_blocks + 1)
            return tuple(range(start, head + 1)), None
        if head <= previous.block_number:
            return (), previous
        lag = head - previous.block_number
        if lag > self.max_catchup_blocks:
            start = max(0, head - self.startup_lookback_blocks + 1)
            self.skipped_stale_blocks += max(0, start - previous.block_number - 1)
            return tuple(range(start, head + 1)), None
        return tuple(range(previous.block_number + 1, head + 1)), previous

    def _fetch_sequence(self, numbers: Sequence[int]) -> tuple[BscMintBlock, ...]:
        blocks = tuple(self.rpc.fetch_block(number) for number in numbers)
        if tuple(item.number for item in blocks) != tuple(numbers):
            raise RuntimeError("BSC mint RPC returned the wrong block sequence")
        return blocks

    def _locations(self, block: BscMintBlock) -> tuple[MintLocation, ...]:
        transactions = tuple(
            item for item in block.transactions
            if is_verified_factory_transaction(item)
        )
        receipts = self.rpc.fetch_receipts(tuple(
            item.transaction_hash for item in transactions
        ))
        if len(receipts) != len(transactions):
            raise RuntimeError("BSC factory receipt set is incomplete")
        observed = utc_datetime(self.clock())
        return tuple(
            location
            for transaction, receipt in zip(transactions, receipts)
            for location in locate_verified_flap_mints(
                block, transaction, receipt, observed_at=observed
            )
        )
