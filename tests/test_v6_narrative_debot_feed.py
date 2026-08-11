from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import stat

import pytest

from debot4.v6.debot.client import DeBotPage
from debot4.v6.domain import DeBotSignal
from debot4.v6.narrative.debot_feed import (
    CHECKPOINT_SCHEMA,
    DEFAULT_POLL_SECONDS,
    DeBotFeedCheckpointError,
    JsonDeBotFeedCheckpoint,
    NarrativeDeBotFeed,
    select_narrative_candidate,
)
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = "0x" + "a" * 40


class FakeClient:
    def __init__(self, responses: list[DeBotPage | Exception]) -> None:
        self.responses = responses
        self.closed = False

    def fetch_page(self, cursor: str | None = None) -> DeBotPage:
        assert cursor is None
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        self.closed = True


class Timer:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float = DEFAULT_POLL_SECONDS) -> None:
        self.value += seconds


def _signal(
    signal_id: str,
    offset: int,
    *,
    kind: str = "kol",
    group: str = "KOL#1min#3",
    qualified: bool = True,
    available_offset: int = 1,
) -> DeBotSignal:
    return DeBotSignal(
        signal_id=signal_id,
        token_address=TOKEN,
        signal_kind=kind,
        group_name=group,
        event_at=NOW + timedelta(seconds=offset),
        available_at=NOW + timedelta(seconds=offset + available_offset),
        channel_id="2",
        pair_address=None,
        dex_name="PancakeSwap",
        token_name="Story Dog",
        token_symbol="DOG",
        token_decimals=18,
        total_supply=Decimal("1000000000"),
        created_at=None,
        provider_fdv_usd=Decimal("100000"),
        provider_liquidity_usd=Decimal("20000"),
        narrative_urls=(),
        description=None,
        wallet_trades=(),
        kol_buy_qualified=qualified,
        kol_buy_reason="test",
    )


def _page(*signals: DeBotSignal, at: datetime = NOW) -> DeBotPage:
    return DeBotPage(tuple(signals), None, at, 100)


def test_first_success_delivers_current_candidates_then_dedupes_later_pages(
    tmp_path: Path,
) -> None:
    baseline = _signal("old", 0)
    later = _signal(
        "smart", 10, kind="smart_money", group="SmartMoney#5min", qualified=False,
    )
    earlier = _signal("kol", 5)
    duplicate = _signal("kol", 8)
    client = FakeClient([
        _page(baseline),
        _page(later, baseline, duplicate, earlier),
        _page(later, earlier),
    ])
    timer = Timer()
    feed = NarrativeDeBotFeed(
        client, tmp_path / "private" / "feed.json", timer=timer
    )

    assert feed.poll_seconds == DEFAULT_POLL_SECONDS == 2.0
    assert [item.signal.signal_id for item in feed.poll_once()] == ["old"]
    assert feed.poll_once() == ()
    assert len(client.responses) == 2
    timer.advance()
    candidates = feed.poll_once(anomaly="  one-minute price acceleration  ")
    assert [item.signal.signal_id for item in candidates] == ["kol", "smart"]
    assert candidates[0].reasons == (
        "qualified_kol", "kol_signal_or_group", "explicit_anomaly",
    )
    assert candidates[1].reasons == (
        "smart_money_signal_or_group", "explicit_anomaly",
    )
    assert all(item.authorizes_trade is False for item in candidates)
    timer.advance()
    assert feed.poll_once(anomaly="still moving") == ()


def test_checkpoint_survives_restart_with_private_permissions(tmp_path: Path) -> None:
    directory = tmp_path / "private"
    path = directory / "debot-feed.json"
    old = _signal("old", 0)
    new = _signal("new", 3)
    first = NarrativeDeBotFeed(FakeClient([_page(old)]), path, poll_seconds=0.001)
    assert [item.signal.signal_id for item in first.poll_once()] == ["old"]

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "schema": CHECKPOINT_SCHEMA,
        "seen_signal_ids": ["old"],
    }
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert stat.S_IMODE(path.stat().st_mode) == 0o600

    restarted = NarrativeDeBotFeed(
        FakeClient([_page(old, new)]), path, poll_seconds=0.001
    )
    assert [item.signal.signal_id for item in restarted.poll_once()] == ["new"]


def test_failed_page_does_not_advance_or_damage_checkpoint(tmp_path: Path) -> None:
    path = tmp_path / "private" / "feed.json"
    old = _signal("old", 0)
    new = _signal("new", 2)
    client = FakeClient([_page(old), RuntimeError("network failed"), _page(old, new)])
    timer = Timer()
    feed = NarrativeDeBotFeed(client, path, timer=timer)
    assert [item.signal.signal_id for item in feed.poll_once()] == ["old"]
    before = path.read_bytes()

    timer.advance()
    with pytest.raises(RuntimeError, match="network failed"):
        feed.poll_once()
    assert path.read_bytes() == before
    timer.advance()
    assert [item.signal.signal_id for item in feed.poll_once()] == ["new"]


def test_accept_failure_keeps_checkpoint_and_queue_retry_is_idempotent(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "private" / "feed.json"
    database = tmp_path / "jobs" / "narrative.sqlite3"
    old = _signal("old", 0)
    first = _signal("first", 2)
    second = _signal("second", 3)
    timer = Timer()
    feed = NarrativeDeBotFeed(
        FakeClient([_page(old), _page(old, first, second), _page(old, first, second)]),
        checkpoint,
        timer=timer,
    )
    assert [item.signal.signal_id for item in feed.poll_once()] == ["old"]
    before = checkpoint.read_bytes()

    with NarrativeJobQueue(database) as queue:
        def partial_accept(candidates) -> None:
            queue.enqueue(candidates[0].signal)
            raise RuntimeError("durable accept interrupted")

        timer.advance()
        with pytest.raises(RuntimeError, match="accept interrupted"):
            feed.poll_once(accept=partial_accept)
        assert checkpoint.read_bytes() == before
        assert queue.counts()[JobStatus.PENDING] == 1

        def complete_accept(candidates) -> None:
            for candidate in candidates:
                queue.enqueue(candidate.signal)

        timer.advance()
        delivered = feed.poll_once(accept=complete_accept)
        assert [item.signal.signal_id for item in delivered] == ["first", "second"]
        assert queue.counts()[JobStatus.PENDING] == 2

    saved = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert saved["seen_signal_ids"] == ["first", "old", "second"]


def test_filter_accepts_debot_narrative_sources_or_anomaly_but_never_trades() -> None:
    unqualified_kol = _signal("kol", 0, qualified=False)
    smart = _signal(
        "smart", 0, kind="unknown", group="SmartMoney#1min", qualified=False,
    )
    unrelated = _signal(
        "other", 0, kind="whale", group="Whale#1min", qualified=False,
    )

    assert select_narrative_candidate(unqualified_kol) is not None
    assert select_narrative_candidate(smart).reasons == (
        "smart_money_signal_or_group",
    )
    assert select_narrative_candidate(unrelated) is None
    anomaly = select_narrative_candidate(unrelated, anomaly="volume spike")
    assert anomaly is not None
    assert anomaly.reasons == ("explicit_anomaly",)
    assert anomaly.authorizes_trade is False


def test_invalid_checkpoint_is_rejected_instead_of_replaying_old_signals(
    tmp_path: Path,
) -> None:
    path = tmp_path / "private" / "feed.json"
    path.parent.mkdir()
    path.write_text('{"schema":"wrong","seen_signal_ids":[]}\n', encoding="utf-8")

    with pytest.raises(DeBotFeedCheckpointError, match="schema"):
        JsonDeBotFeedCheckpoint(path)


def test_close_delegates_to_the_shared_debot_client(tmp_path: Path) -> None:
    client = FakeClient([])
    feed = NarrativeDeBotFeed(client, tmp_path / "private" / "feed.json")
    feed.close()
    assert client.closed is True
