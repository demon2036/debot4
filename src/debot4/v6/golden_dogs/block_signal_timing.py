"""Pure executability gate for an on-chain signal relative to price motion."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BlockSignalStage(str, Enum):
    PREVIOUS_BLOCK = "previous_block"
    SAME_BLOCK_BEFORE = "same_block_before"
    SAME_TRANSACTION_OR_AFTER = "same_transaction_or_after"


@dataclass(frozen=True, slots=True)
class BlockSignalTiming:
    stage: BlockSignalStage
    post_confirmation_actionable: bool
    mempool_or_builder_only: bool
    block_lead: int
    transaction_lead: int | None


def classify_block_signal(
    signal_block: int,
    signal_transaction_index: int,
    motion_block: int,
    motion_transaction_index: int,
) -> BlockSignalTiming:
    """Count only an earlier block as observable after normal confirmation."""

    values = (
        signal_block, signal_transaction_index,
        motion_block, motion_transaction_index,
    )
    if any(value < 0 for value in values) or signal_block == 0 or motion_block == 0:
        raise ValueError("block positions must be non-negative and mined")
    block_lead = motion_block - signal_block
    transaction_lead = None
    if signal_block < motion_block:
        stage = BlockSignalStage.PREVIOUS_BLOCK
    elif (
        signal_block == motion_block
        and signal_transaction_index < motion_transaction_index
    ):
        stage = BlockSignalStage.SAME_BLOCK_BEFORE
        transaction_lead = motion_transaction_index - signal_transaction_index
    else:
        stage = BlockSignalStage.SAME_TRANSACTION_OR_AFTER
        if signal_block == motion_block:
            transaction_lead = motion_transaction_index - signal_transaction_index
    return BlockSignalTiming(
        stage=stage,
        post_confirmation_actionable=stage == BlockSignalStage.PREVIOUS_BLOCK,
        mempool_or_builder_only=stage == BlockSignalStage.SAME_BLOCK_BEFORE,
        block_lead=block_lead,
        transaction_lead=transaction_lead,
    )
