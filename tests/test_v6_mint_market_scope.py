from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from decimal import Decimal

from debot4.v6.dex_audit.models import Board, Gainer
from debot4.v6.narrative.market_signal import MarketQualityPolicy
from debot4.v6.narrative.mint_market_scope import scope_recent_mint_candidates
from tests.v6_catalyst_mint_samples import BUDUJIN_CA, BUDUJIN_MINT_AT


def _gainer(**changes: object) -> Gainer:
    values = {
        "token_address": BUDUJIN_CA,
        "pair_address": None,
        "symbol": "不对劲",
        "name": "SEED ALPHA",
        "h1_change_pct": Decimal("100"),
        "liquidity_usd": Decimal("50000"),
        "fdv_usd": Decimal("500000"),
        "market_cap_usd": Decimal("500000"),
        "price_usd": Decimal("0.01"),
        "volume_h1_usd": Decimal("20000"),
        "txns_h1": 20,
        "published_at_us": int(BUDUJIN_MINT_AT.timestamp() * 1_000_000),
    }
    values.update(changes)
    return Gainer(**values)


def _scope(row: Gainer, *, now_offset: timedelta = timedelta(minutes=1)):
    now = BUDUJIN_MINT_AT + now_offset
    board = Board(
        as_of_us=int(now.timestamp() * 1_000_000),
        source="coinmarketcap_datahub",
        source_url="https://example.invalid/market-board",
        universe="bsc_1h",
        ranking_exact=True,
        rows=(row,),
        attempts=(),
    )
    selection = MarketQualityPolicy().select(board)
    return scope_recent_mint_candidates(
        selection.anomalies,
        board.rows,
        now=now,
        policy_started_at=BUDUJIN_MINT_AT - timedelta(seconds=10),
    )


def test_recent_published_mint_is_eligible() -> None:
    scope = _scope(_gainer())

    assert [item.exact_ca for item in scope.eligible] == [BUDUJIN_CA]
    assert scope.exclusions == ()


def test_missing_publish_time_is_explicitly_excluded() -> None:
    scope = _scope(replace(_gainer(), published_at_us=None))

    assert scope.eligible == ()
    assert scope.exclusions[0].reason == "published_at_missing"


def test_future_publish_time_is_explicitly_excluded() -> None:
    future = BUDUJIN_MINT_AT + timedelta(minutes=5)
    scope = _scope(replace(
        _gainer(), published_at_us=int(future.timestamp() * 1_000_000)
    ))

    assert scope.eligible == ()
    assert scope.exclusions[0].reason == "published_at_in_future"


def test_publish_time_older_than_recent_window_is_excluded() -> None:
    scope = _scope(_gainer(), now_offset=timedelta(hours=2, seconds=1))

    assert scope.eligible == ()
    assert scope.exclusions[0].reason == "published_before_recent_window"
