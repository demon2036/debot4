from dataclasses import replace

import pytest

from debot4.v6.golden_dogs.kol_identity import (
    CHINESE_MEME_KOL_CANDIDATES,
    IdentityTier,
    LOOKONCHAIN_BSC_TRADERS,
)
from debot4.v6.golden_dogs.kol_search import chinese_kol_search_tasks
from datetime import date


def test_three_reviewed_bsc_traders_keep_exact_wallets_and_aliases() -> None:
    by_handle = {item.handle.casefold(): item for item in LOOKONCHAIN_BSC_TRADERS}

    assert set(by_handle) == {"hexiecs", "brc20niubi", "gcsheng"}
    assert by_handle["gcsheng"].wallet == (
        "0x51fbb0b8164231c116acdce55db3d5c0d9650987"
    )
    assert "深大高材生" in by_handle["gcsheng"].aliases
    assert all(item.tier is IdentityTier.WALLET_ATTRIBUTED for item in by_handle.values())


def test_wallet_attribution_cannot_exist_without_source() -> None:
    with pytest.raises(ValueError, match="wallet attribution"):
        replace(LOOKONCHAIN_BSC_TRADERS[0], attribution_url=None)


def test_chinese_candidate_list_is_x_verified_but_not_wallet_inferred() -> None:
    candidates = tuple(CHINESE_MEME_KOL_CANDIDATES)

    assert len(candidates) == 24
    assert len({item.stable_user_id for item in candidates}) == 24
    assert all(item.tier is IdentityTier.X_VERIFIED for item in candidates)
    assert all(item.wallet is None for item in candidates)


def test_chinese_kol_scan_has_omission_sweeps_and_every_reviewed_handle() -> None:
    tasks = chinese_kol_search_tasks(date(2025, 8, 12), date(2026, 8, 13))
    handle_tasks = tuple(item for item in tasks if item.key.startswith("handle:"))

    assert len(tasks) == 50
    assert len(handle_tasks) == 27
    assert len({item.key for item in tasks}) == len(tasks)
    assert all("token contract" in item.prompt for item in tasks)
    assert all("wallet" in item.prompt for item in tasks)
    assert len(tuple(item for item in tasks if item.key.startswith("period:"))) == 5
    assert any(item.key == "omission:reply-quote-network" for item in tasks)
