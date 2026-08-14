from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from debot4.v6.narrative.chain_mint import (
    FLAP_FACTORY,
    TRANSFER_TOPIC,
    ZERO_TOPIC,
    BscMintBlock,
    BscMintLog,
    BscMintReceipt,
    BscMintTransaction,
)
from debot4.v6.narrative.chain_mint_monitor import BscFactoryMintMonitor
from debot4.v6.narrative.chain_mint_state import (
    ChainMintCheckpoint,
    ChainMintCheckpointStore,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 14, 5, 0, tzinfo=UTC)
CA = "0x417bda357cce720467edc56ebc6bb4c9ea497777"


class _Timer:
    value = 0.0

    def __call__(self) -> float:
        return self.value


class _Rpc:
    def __init__(
        self,
        blocks: tuple[BscMintBlock, ...],
        receipts: tuple[BscMintReceipt, ...] = (),
    ) -> None:
        self.blocks = {item.number: item for item in blocks}
        self.receipts = {item.transaction_hash: item for item in receipts}
        self.head_calls = 0
        self.block_calls: list[int] = []
        self.receipt_calls: list[tuple[str, ...]] = []

    def latest_block_number(self) -> int:
        self.head_calls += 1
        return max(self.blocks)

    def fetch_block(self, number: int) -> BscMintBlock:
        self.block_calls.append(number)
        return self.blocks[number]

    def fetch_receipts(
        self, transaction_hashes: tuple[str, ...]
    ) -> tuple[BscMintReceipt, ...]:
        self.receipt_calls.append(transaction_hashes)
        return tuple(self.receipts[item] for item in transaction_hashes)


def _hash(number: int) -> str:
    return "0x" + format(number, "064x")


def _mint_block(number: int = 10) -> tuple[BscMintBlock, BscMintReceipt]:
    transaction_hash = "0x" + "a" * 64
    transaction = BscMintTransaction(transaction_hash, FLAP_FACTORY, 7)
    block = BscMintBlock(
        number, _hash(number), _hash(number - 1), NOW, (transaction,)
    )
    receipt = BscMintReceipt(
        transaction_hash, FLAP_FACTORY, True, number, block.block_hash, 7,
        (BscMintLog(
            CA, (TRANSFER_TOPIC, ZERO_TOPIC, "0x" + "b" * 64),
            "0x01", transaction_hash,
        ),),
    )
    return block, receipt


def _empty_blocks(start: int, end: int) -> tuple[BscMintBlock, ...]:
    return tuple(
        BscMintBlock(
            number, _hash(number), _hash(number - 1), NOW, ()
        )
        for number in range(start, end + 1)
    )


def test_location_reaches_callback_before_checkpoint_and_restart_deduplicates(
    tmp_path: Path,
) -> None:
    block, receipt = _mint_block()
    rpc = _Rpc((block,), (receipt,))
    path = tmp_path / "cursor.json"
    checkpoints = ChainMintCheckpointStore(path)
    monitor = BscFactoryMintMonitor(
        rpc, checkpoints, startup_lookback_blocks=1,
        clock=lambda: NOW,
    )
    accepted = []

    def persist(locations: tuple[object, ...]) -> None:
        assert checkpoints.load() is None
        accepted.extend(locations)

    found = monitor.poll_once(persist)

    assert found == tuple(accepted)
    assert len(found) == 1 and found[0].exact_ca == CA
    assert checkpoints.load() == ChainMintCheckpoint(10, _hash(10))
    restarted = BscFactoryMintMonitor(
        rpc, ChainMintCheckpointStore(path), startup_lookback_blocks=1,
        clock=lambda: NOW,
    )
    assert restarted.poll_once(accepted.extend) == ()
    assert len(accepted) == 1


def test_callback_failure_never_advances_checkpoint(tmp_path: Path) -> None:
    block, receipt = _mint_block()
    checkpoints = ChainMintCheckpointStore(tmp_path / "cursor.json")
    monitor = BscFactoryMintMonitor(
        _Rpc((block,), (receipt,)), checkpoints,
        startup_lookback_blocks=1,
        clock=lambda: NOW,
    )

    def fail(_locations: object) -> None:
        raise RuntimeError("durable store failed")

    with pytest.raises(RuntimeError, match="durable store"):
        monitor.poll_once(fail)
    assert checkpoints.load() is None


def test_empty_blocks_checkpoint_and_poll_is_self_throttled(tmp_path: Path) -> None:
    timer = _Timer()
    block = _empty_blocks(10, 10)[0]
    rpc = _Rpc((block,))
    checkpoints = ChainMintCheckpointStore(tmp_path / "cursor.json")
    monitor = BscFactoryMintMonitor(
        rpc, checkpoints, poll_seconds=0.25, startup_lookback_blocks=1,
        timer=timer,
    )

    assert monitor.poll_once(lambda _items: None) == ()
    assert checkpoints.load() == ChainMintCheckpoint(10, _hash(10))
    timer.value = 0.249
    assert monitor.poll_once(lambda _items: None) == ()
    assert rpc.head_calls == 1
    timer.value = 0.25
    assert monitor.poll_once(lambda _items: None) == ()
    assert rpc.head_calls == 2
    assert rpc.receipt_calls == [()]


def test_stale_checkpoint_uses_bounded_recent_catchup(tmp_path: Path) -> None:
    path = tmp_path / "cursor.json"
    checkpoints = ChainMintCheckpointStore(path)
    checkpoints.save(ChainMintCheckpoint(1, _hash(1)))
    rpc = _Rpc(_empty_blocks(98, 100))
    monitor = BscFactoryMintMonitor(
        rpc, checkpoints, startup_lookback_blocks=3, max_catchup_blocks=4
    )

    assert monitor.poll_once(lambda _items: None) == ()
    assert rpc.block_calls == [98, 99, 100]
    assert checkpoints.load() == ChainMintCheckpoint(100, _hash(100))
    assert monitor.skipped_stale_blocks == 96
    assert monitor.snapshot()["finality"] == "included_not_finalized"
    assert monitor.snapshot()["authorizes_trade"] is False


def test_parent_mismatch_replays_bounded_canonical_window(tmp_path: Path) -> None:
    path = tmp_path / "cursor.json"
    checkpoints = ChainMintCheckpointStore(path)
    checkpoints.save(ChainMintCheckpoint(9, "0x" + "f" * 64))
    rpc = _Rpc(_empty_blocks(8, 10))
    monitor = BscFactoryMintMonitor(
        rpc, checkpoints, startup_lookback_blocks=3,
    )

    assert monitor.poll_once(lambda _items: None) == ()
    assert rpc.block_calls == [10, 8, 9, 10]
    assert monitor.reorg_recoveries == 1
    assert checkpoints.load() == ChainMintCheckpoint(10, _hash(10))
