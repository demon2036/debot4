from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.narrative.chain_mint import (
    FLAP_FACTORY,
    TRANSFER_TOPIC,
    ZERO_TOPIC,
    BscMintBlock,
    BscMintLog,
    BscMintReceipt,
    BscMintTransaction,
    locate_verified_flap_mints,
)
from debot4.v6.narrative.debot_mint_location import location_from_debot
from debot4.v6.narrative.mint_location import (
    BSC_FACTORY_SOURCE,
    DEBOT_NEW_SOURCE,
    MintLocation,
)
from debot4.v6.narrative.mint_location_store import (
    MintLocationConflict,
    MintLocationStore,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 14, 5, 0, tzinfo=UTC)
CA = "0x417bda357cce720467edc56ebc6bb4c9ea497777"
TX = "0x491c4a5ef3bc98cbd00abcc9507863051a28b308217ca4dd0f6515193e3cd233"
BLOCK_HASH = "0x" + "1" * 64
PARENT_HASH = "0x" + "2" * 64


def _snapshot(
    *,
    fetched_at: datetime = NOW,
    created_at: datetime | None = None,
    social_urls: tuple[str, ...] = (),
) -> RankSnapshot:
    return RankSnapshot(
        CA, "new", fetched_at, "No Link", "NL", 0, (), None,
        Decimal("4200"), False, created_at, "flap", None, social_urls,
    )


def _chain_inputs(
    *, factory: str = FLAP_FACTORY, succeeded: bool = True,
) -> tuple[BscMintBlock, BscMintTransaction, BscMintReceipt]:
    transaction = BscMintTransaction(TX, factory, 52)
    logs = (
        BscMintLog(
            "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c",
            (TRANSFER_TOPIC, ZERO_TOPIC, "0x" + "4" * 64),
            "0x01", TX,
        ),
        BscMintLog(
            CA, (TRANSFER_TOPIC, ZERO_TOPIC, "0x" + "4" * 64),
            "0x3b9aca00", TX,
        ),
        BscMintLog(
            "0xaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa7777",
            (TRANSFER_TOPIC, "0x" + "5" * 64, "0x" + "4" * 64),
            "0x10", TX,
        ),
    )
    block = BscMintBlock(
        115_824_174, BLOCK_HASH, PARENT_HASH, NOW, (transaction,)
    )
    receipt = BscMintReceipt(
        TX, factory, succeeded, block.number, BLOCK_HASH, 52, logs
    )
    return block, transaction, receipt


def test_debot_location_keeps_exact_ca_without_social_or_creation_time() -> None:
    location = location_from_debot(_snapshot())

    assert location.exact_ca == CA
    assert location.source == DEBOT_NEW_SOURCE
    assert location.created_at is None
    assert location.social_urls == ()
    assert location.authorizes_trade is False


def test_reviewed_flap_receipt_extracts_token_not_other_zero_transfers() -> None:
    block, transaction, receipt = _chain_inputs()

    (location,) = locate_verified_flap_mints(
        block, transaction, receipt, observed_at=NOW + timedelta(seconds=1)
    )

    assert location.exact_ca == CA
    assert location.source == BSC_FACTORY_SOURCE
    assert location.transaction_hash == TX
    assert location.block_number == block.number
    assert location.transaction_index == 52
    assert location.factory_address == FLAP_FACTORY
    assert location.created_at == NOW
    assert location.authorizes_trade is False


@pytest.mark.parametrize("failure", ["wrong_factory", "failed", "wrong_block"])
def test_chain_rule_fails_closed_on_unverified_receipt(failure: str) -> None:
    block, transaction, receipt = _chain_inputs(
        factory=(
            "0x1111111111111111111111111111111111111111"
            if failure == "wrong_factory" else FLAP_FACTORY
        ),
        succeeded=failure != "failed",
    )
    if failure == "wrong_block":
        receipt = BscMintReceipt(
            receipt.transaction_hash, receipt.to_address, True,
            block.number + 1, receipt.block_hash,
            receipt.transaction_index, receipt.logs,
        )

    assert locate_verified_flap_mints(
        block, transaction, receipt, observed_at=NOW
    ) == ()


def test_store_keeps_no_link_ca_then_enriches_without_hot_loop_writes(
    tmp_path: Path,
) -> None:
    database = tmp_path / "private" / "mint.sqlite3"
    clock = lambda: NOW + timedelta(minutes=2)
    first = location_from_debot(_snapshot())
    repeated = location_from_debot(_snapshot(
        fetched_at=NOW + timedelta(seconds=10)
    ))
    linked = location_from_debot(_snapshot(
        fetched_at=NOW + timedelta(seconds=20),
        created_at=NOW - timedelta(seconds=5),
        social_urls=("https://x.com/flapdotsh/status/1234567890",),
    ))
    with MintLocationStore(database, clock=clock) as store:
        assert store.record((first,)).inserted == 1
        assert store.record((repeated,)).unchanged == 1
        assert store.record((linked,)).enriched == 1
        snapshot = store.snapshot()
        assert snapshot["observations"] == 1
        assert snapshot["unique_exact_cas"] == 1
        assert snapshot["by_source"][DEBOT_NEW_SOURCE] == 1
        assert snapshot["max_database_bytes"] <= 64 * 1_024 * 1_024

    with MintLocationStore(database, clock=clock) as restarted:
        (stored,) = restarted.recent(
            NOW - timedelta(minutes=1), NOW + timedelta(minutes=1)
        )
        assert stored.exact_ca == CA
        assert stored.created_at == NOW - timedelta(seconds=5)
        assert stored.social_urls == (
            "https://x.com/flapdotsh/status/1234567890",
        )


def test_store_keeps_reincluded_transaction_as_distinct_reorg_evidence(
    tmp_path: Path,
) -> None:
    block, transaction, receipt = _chain_inputs()
    (location,) = locate_verified_flap_mints(
        block, transaction, receipt, observed_at=NOW
    )
    database = tmp_path / "mint.sqlite3"
    with MintLocationStore(database, clock=lambda: NOW) as store:
        store.record((location,))
        reincluded = MintLocation(
            exact_ca=CA, source=BSC_FACTORY_SOURCE, observed_at=NOW,
            created_at=NOW, launchpad="flap", transaction_hash=TX,
            block_number=block.number, block_hash="0x" + "9" * 64,
            transaction_index=52, factory_address=FLAP_FACTORY,
        )
        assert store.record((reincluded,)).inserted == 1
        assert store.snapshot()["observations"] == 2


def test_store_rejects_same_receipt_identity_with_changed_position(
    tmp_path: Path,
) -> None:
    block, transaction, receipt = _chain_inputs()
    (location,) = locate_verified_flap_mints(
        block, transaction, receipt, observed_at=NOW
    )
    database = tmp_path / "mint.sqlite3"
    with MintLocationStore(database, clock=lambda: NOW) as store:
        store.record((location,))
        contradictory = MintLocation(
            exact_ca=CA, source=BSC_FACTORY_SOURCE, observed_at=NOW,
            created_at=NOW, launchpad="flap", transaction_hash=TX,
            block_number=block.number + 1, block_hash=BLOCK_HASH,
            transaction_index=52, factory_address=FLAP_FACTORY,
        )
        with pytest.raises(MintLocationConflict):
            store.record((contradictory,))
