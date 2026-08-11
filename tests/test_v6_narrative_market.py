from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import stat

import pytest

from debot4.v6.dex_audit.models import Board, Gainer
from debot4.v6.narrative.market_monitor import MarketAnomalyMonitor
from debot4.v6.narrative.market_signal import MarketQualityPolicy


NOW = datetime(2026, 8, 10, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


def _row(**changes: object) -> Gainer:
    values = {
        "token_address": TOKEN,
        "pair_address": None,
        "symbol": "DOGO",
        "name": "Dogo",
        "h1_change_pct": Decimal("5.14"),
        "liquidity_usd": Decimal("170800"),
        "fdv_usd": Decimal("2200000"),
        "market_cap_usd": Decimal("2200000"),
        "price_usd": Decimal("0.0022"),
        "volume_h1_usd": Decimal("45000"),
        "txns_h1": 120,
    }
    values.update(changes)
    return Gainer(**values)


def _board(*rows: Gainer, exact: bool = True) -> Board:
    return Board(
        as_of_us=int(NOW.timestamp() * 1_000_000),
        source="coinmarketcap_datahub" if exact else "geckoterminal",
        source_url="https://dapi.coinmarketcap.com/dex/v1/test",
        universe="bsc_1h_gainers",
        ranking_exact=exact,
        rows=rows,
        attempts=(),
    )


def test_quality_gate_keeps_usable_mover_and_rejects_manipulated_rankings() -> None:
    policy = MarketQualityPolicy()
    inflated = _row(
        token_address="0x" + "34" * 20,
        symbol="TUT",
        h1_change_pct=Decimal("5000000"),
        liquidity_usd=Decimal("100000"),
        market_cap_usd=Decimal("13000000000"),
        fdv_usd=Decimal("13000000000"),
        txns_h1=30,
    )
    inactive = _row(
        token_address="0x" + "56" * 20,
        symbol="QUIET",
        txns_h1=2,
    )

    selected = policy.select(_board(inflated, inactive, _row()))

    assert [item.symbol for item in selected.anomalies] == ["DOGO"]
    assert selected.anomalies[0].stage_pct == Decimal("5")
    reasons = {item.reason for item in selected.rejections}
    assert "valuation_liquidity_ratio_too_high" in reasons
    assert "transactions_below_threshold" in reasons


def test_fallback_board_never_becomes_a_global_gainer_trigger() -> None:
    selected = MarketQualityPolicy().select(_board(_row(), exact=False))
    assert selected.anomalies == ()
    assert selected.rejections[0].reason == "board_not_exact"


def test_stage_identity_is_stable_within_day_and_changes_at_new_threshold() -> None:
    policy = MarketQualityPolicy()
    first = policy.select(_board(_row())).anomalies[0]
    refreshed = policy.select(_board(replace(
        _row(), h1_change_pct=Decimal("9"), volume_h1_usd=Decimal("65000")
    ))).anomalies[0]
    higher = policy.select(_board(replace(
        _row(), h1_change_pct=Decimal("10.1")
    ))).anomalies[0]
    tomorrow = policy.select(replace(
        _board(_row()),
        as_of_us=int((NOW + timedelta(days=1)).timestamp() * 1_000_000),
    )).anomalies[0]

    assert first.anomaly_id == refreshed.anomaly_id
    assert higher.anomaly_id != first.anomaly_id
    assert tomorrow.anomaly_id != first.anomaly_id


def test_monitor_self_throttles_and_checkpoints_only_after_accept(
    tmp_path: Path,
) -> None:
    ticks = [0.0]
    fetches: list[int] = []

    def fetcher(_client: object, *, as_of_us: int, limit: int) -> Board:
        fetches.append(limit)
        return _board(_row())

    checkpoint = tmp_path / "private" / "market.json"
    monitor = MarketAnomalyMonitor(
        checkpoint,
        client=object(),
        poll_seconds=5,
        fetcher=fetcher,
        clock=lambda: NOW,
        timer=lambda: ticks[0],
    )
    accepted: list[tuple[object, ...]] = []

    first = monitor.poll_once(accept=accepted.append)
    assert len(first) == 1 and len(fetches) == 1
    assert monitor.poll_once(accept=accepted.append) == ()
    assert len(fetches) == 1
    ticks[0] = 5
    assert monitor.poll_once(accept=accepted.append) == ()
    assert len(fetches) == 2 and len(accepted) == 2
    assert stat.S_IMODE(checkpoint.stat().st_mode) == 0o600


def test_failed_queue_accept_does_not_lose_market_anomaly(tmp_path: Path) -> None:
    ticks = [0.0]
    monitor = MarketAnomalyMonitor(
        tmp_path / "market.json",
        client=object(),
        poll_seconds=1,
        fetcher=lambda *_args, **_kwargs: _board(_row()),
        clock=lambda: NOW,
        timer=lambda: ticks[0],
    )

    with pytest.raises(OSError, match="queue unavailable"):
        monitor.poll_once(accept=lambda _items: (_ for _ in ()).throw(
            OSError("queue unavailable")
        ))
    assert monitor.state.snapshot() == ()

    ticks[0] = 1
    assert len(monitor.poll_once(accept=lambda _items: None)) == 1
    assert len(monitor.state.snapshot()) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"stages": (Decimal("5"),), "min_change_pct": Decimal("3")},
        {"stages": (Decimal("5"), Decimal("5"))},
        {"stages": (Decimal("0"),)},
    ],
)
def test_invalid_market_stages_fail_closed(changes: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        MarketQualityPolicy(**changes)
