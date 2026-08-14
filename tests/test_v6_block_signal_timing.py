from debot4.v6.golden_dogs.block_signal_timing import (
    BlockSignalStage,
    classify_block_signal,
)


def test_previous_block_is_post_confirmation_actionable() -> None:
    result = classify_block_signal(100, 9, 102, 1)
    assert result.stage == BlockSignalStage.PREVIOUS_BLOCK
    assert result.post_confirmation_actionable is True
    assert result.block_lead == 2


def test_earlier_transaction_in_same_block_is_mempool_only() -> None:
    result = classify_block_signal(100, 3, 100, 8)
    assert result.stage == BlockSignalStage.SAME_BLOCK_BEFORE
    assert result.post_confirmation_actionable is False
    assert result.mempool_or_builder_only is True
    assert result.transaction_lead == 5


def test_same_or_later_position_is_not_advance() -> None:
    result = classify_block_signal(100, 8, 100, 8)
    assert result.stage == BlockSignalStage.SAME_TRANSACTION_OR_AFTER
    assert result.post_confirmation_actionable is False
