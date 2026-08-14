from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.narrative.chain_mint import (
    BscMintBlock,
    BscZeroTransferLog,
    locate_flap_mint_logs,
)
from debot4.v6.narrative.debot_mint_location import location_from_debot
from debot4.v6.narrative.mint_location import (
    BSC_LOG_SOURCE,
    DEBOT_NEW_SOURCE,
    MintLocation,
)
from debot4.v6.narrative.mint_location_store import (
    MintLocationConflict,
    MintLocationStore,
)


UTC = timezone.utc
NOW = datetime(2026, 8, 14, 5, 33, 42, tzinfo=UTC)
CA = "0x4c0b22ad1e202995f1da83556cf1469b00dd7777"
TX = "0x223b58112b4d472f7cb98548a1bc1e1ff7627dc3167b945ea733f46bb79c747b"
BLOCK_HASH = "0x19a9e68effb5bdb5e5fcbe130f30446e295db5de5f8f5d39c8780e43f9cd8b2e"
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
    *, exact_ca: str = CA, data: str = "0x" + "0" * 63 + "1",
) -> tuple[BscMintBlock, BscZeroTransferLog]:
    block = BscMintBlock(
        115_833_252, BLOCK_HASH, PARENT_HASH, NOW
    )
    mint_log = BscZeroTransferLog(
        exact_ca, TX, block.number, BLOCK_HASH, 93, 539, data
    )
    return block, mint_log


def test_debot_location_keeps_exact_ca_without_social_or_creation_time() -> None:
    location = location_from_debot(_snapshot())

    assert location.exact_ca == CA
    assert location.source == DEBOT_NEW_SOURCE
    assert location.created_at is None
    assert location.social_urls == ()
    assert location.authorizes_trade is False


def test_route_independent_log_extracts_real_current_flap_ca() -> None:
    block, mint_log = _chain_inputs()

    (location,) = locate_flap_mint_logs(
        block, (mint_log,), observed_at=NOW + timedelta(seconds=1)
    )

    assert location.exact_ca == CA
    assert location.source == BSC_LOG_SOURCE
    assert location.transaction_hash == TX
    assert location.block_number == block.number
    assert location.transaction_index == 93
    assert location.factory_address is None
    assert location.launchpad is None
    assert location.created_at == NOW
    assert location.authorizes_trade is False


@pytest.mark.parametrize(
    ("exact_ca", "data"),
    [
        ("0x4c0b22ad1e202995f1da83556cf1469b00dd7778", "0x" + "0" * 63 + "1"),
        (CA, "0x" + "0" * 64),
    ],
)
def test_chain_rule_ignores_non_flap_or_zero_quantity_logs(
    exact_ca: str, data: str,
) -> None:
    block, mint_log = _chain_inputs(exact_ca=exact_ca, data=data)

    assert locate_flap_mint_logs(
        block, (mint_log,), observed_at=NOW
    ) == ()


def test_chain_rule_rejects_log_from_a_different_block() -> None:
    block, mint_log = _chain_inputs()
    wrong = BscZeroTransferLog(
        mint_log.token_address, mint_log.transaction_hash,
        block.number + 1, mint_log.block_hash,
        mint_log.transaction_index, mint_log.log_index, mint_log.data,
    )

    with pytest.raises(ValueError, match="does not belong"):
        locate_flap_mint_logs(block, (wrong,), observed_at=NOW)


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
    block, mint_log = _chain_inputs()
    (location,) = locate_flap_mint_logs(
        block, (mint_log,), observed_at=NOW
    )
    database = tmp_path / "mint.sqlite3"
    with MintLocationStore(database, clock=lambda: NOW) as store:
        store.record((location,))
        reincluded = MintLocation(
            exact_ca=CA, source=BSC_LOG_SOURCE, observed_at=NOW,
            created_at=NOW, launchpad="flap", transaction_hash=TX,
            block_number=block.number, block_hash="0x" + "9" * 64,
            transaction_index=93,
        )
        assert store.record((reincluded,)).inserted == 1
        assert store.snapshot()["observations"] == 2


def test_store_rejects_same_receipt_identity_with_changed_position(
    tmp_path: Path,
) -> None:
    block, mint_log = _chain_inputs()
    (location,) = locate_flap_mint_logs(
        block, (mint_log,), observed_at=NOW
    )
    database = tmp_path / "mint.sqlite3"
    with MintLocationStore(database, clock=lambda: NOW) as store:
        store.record((location,))
        contradictory = MintLocation(
            exact_ca=CA, source=BSC_LOG_SOURCE, observed_at=NOW,
            created_at=NOW, launchpad="flap", transaction_hash=TX,
            block_number=block.number + 1, block_hash=BLOCK_HASH,
            transaction_index=93,
        )
        with pytest.raises(MintLocationConflict):
            store.record((contradictory,))
