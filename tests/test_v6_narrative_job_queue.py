from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
from pathlib import Path
import sqlite3
import stat

import pytest

from debot4.v6.domain import DeBotSignal, WalletTrade
from debot4.v6.narrative.job_payloads import (
    ACTIVE_X_POST,
    PASSIVE_DEBOT_SIGNAL,
)
from debot4.v6.narrative.job_queue import (
    JobContentConflict,
    JobStatus,
    LeaseLostError,
    NarrativeJobQueue,
)
from debot4.v6.x.models import XPost


NOW = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)
TOKEN = "0x" + "12" * 20


@dataclass
class Clock:
    value: datetime = NOW

    def __call__(self) -> datetime:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += timedelta(seconds=seconds)


def _post(tweet_id: str = "123456789") -> XPost:
    return XPost(
        tweet_id=tweet_id,
        author="cz_binance",
        text="A builder just shipped something culturally important.",
        created_at=NOW - timedelta(seconds=2),
        fetched_at=NOW,
        post_type="quote",
        target_author="bnbchain",
        target_text="Launch day",
        urls=("https://example.test/context",),
        bsc_contracts=(TOKEN,),
    )


def _signal() -> DeBotSignal:
    wallet = WalletTrade(
        alias="KOL-1234",
        wallet="0x" + "34" * 20,
        traded_at=NOW - timedelta(seconds=1),
        volume_usd=Decimal("812.50"),
        token_amount=Decimal("2000000"),
    )
    return DeBotSignal(
        signal_id="debot-signal-1",
        token_address=TOKEN,
        signal_kind="kol_buy",
        group_name="KOL#5min#800#100K",
        event_at=NOW - timedelta(seconds=1),
        available_at=NOW,
        channel_id="2",
        pair_address="0x" + "56" * 20,
        dex_name="PancakeSwap",
        token_name="Narrative Dog",
        token_symbol="NDOG",
        token_decimals=18,
        total_supply=Decimal("1000000000"),
        created_at=NOW - timedelta(minutes=20),
        provider_fdv_usd=Decimal("100000"),
        provider_liquidity_usd=Decimal("25000"),
        narrative_urls=("https://x.com/example/status/123456789",),
        description="A sudden market anomaly requiring narrative research",
        wallet_trades=(wallet,),
        kol_buy_qualified=True,
        kol_buy_reason="provider reported historical KOL participation",
        security_hint={"is_honeypot": "0"},
        raw_context={"source": "debot", "rows": [1, 2]},
    )


def _queue(tmp_path: Path, clock: Clock) -> NarrativeJobQueue:
    return NarrativeJobQueue(tmp_path / "private" / "jobs.sqlite3", clock=clock)


def test_content_addressed_dedup_and_typed_json_round_trip(tmp_path: Path) -> None:
    clock = Clock()
    with _queue(tmp_path, clock) as queue:
        active_id = queue.enqueue(_post())
        assert queue.enqueue(_post(), max_attempts=9) == active_id
        passive_id = queue.enqueue(_signal())
        assert active_id.startswith("narrative-job-") and len(active_id) == 78
        assert active_id != passive_id
        assert queue.counts()[JobStatus.PENDING] == 2

        active = queue.claim("grok-worker", lease_seconds=30)
        assert active is not None
        assert active.kind == ACTIVE_X_POST
        assert active.payload == _post()
        assert active.lease_id is not None
        queue.ack(active.job_id, "grok-worker", active.lease_id)

        passive = queue.claim("grok-worker", lease_seconds=30)
        assert passive is not None
        assert passive.kind == PASSIVE_DEBOT_SIGNAL
        assert passive.payload == _signal()
        assert passive.lease_id is not None
        queue.ack(passive.job_id, "grok-worker", passive.lease_id)

    database = tmp_path / "private" / "jobs.sqlite3"
    with sqlite3.connect(database) as db:
        documents = [row[0] for row in db.execute("SELECT payload_json FROM narrative_jobs")]
    assert all(json.loads(document)["schema"].endswith(".v1") for document in documents)


def test_private_file_permissions_and_file_backing_are_enforced(tmp_path: Path) -> None:
    clock = Clock()
    folder = tmp_path / "queue-private"
    database = folder / "jobs.sqlite3"
    with NarrativeJobQueue(database, clock=clock):
        assert stat.S_IMODE(folder.stat().st_mode) == 0o700
        assert stat.S_IMODE(database.stat().st_mode) == 0o600
    with pytest.raises(ValueError, match="file-backed"):
        NarrativeJobQueue(":memory:", clock=clock)


def test_claim_is_exclusive_and_ack_requires_the_live_owner(tmp_path: Path) -> None:
    clock = Clock()
    database = tmp_path / "private" / "jobs.sqlite3"
    with NarrativeJobQueue(database, clock=clock) as first, NarrativeJobQueue(
        database, clock=clock
    ) as second:
        job_id = first.enqueue(_post())
        claimed = first.claim("worker-a", lease_seconds=10)
        assert claimed is not None and claimed.job_id == job_id
        assert claimed.lease_id is not None
        assert second.claim("worker-b", lease_seconds=10) is None
        with pytest.raises(LeaseLostError):
            second.ack(job_id, "worker-b", claimed.lease_id)
        assert first.get(job_id).status is JobStatus.LEASED
        done = first.ack(job_id, "worker-a", claimed.lease_id)
        assert done.status is JobStatus.DONE
        assert done.completed_at == NOW


def test_expired_leases_retry_then_fail_at_max_attempts(tmp_path: Path) -> None:
    clock = Clock()
    with _queue(tmp_path, clock) as queue:
        job_id = queue.enqueue(_post(), max_attempts=2)
        first = queue.claim("worker-a", lease_seconds=5)
        assert first is not None and first.attempts == 1
        clock.advance(6)
        second = queue.claim("worker-b", lease_seconds=5)
        assert second is not None and second.job_id == job_id
        assert second.attempts == 2 and second.error_type is None
        clock.advance(6)
        assert queue.claim("worker-c", lease_seconds=5) is None
        failed = queue.get(job_id)
        assert failed is not None
        assert failed.status is JobStatus.FAILED
        assert failed.attempts == 2
        assert failed.error_type == "LeaseExpired"


def test_failure_never_persists_exception_messages_or_execution_data(tmp_path: Path) -> None:
    clock = Clock()
    database = tmp_path / "private" / "jobs.sqlite3"
    with NarrativeJobQueue(database, clock=clock) as queue:
        job_id = queue.enqueue(_post(), max_attempts=2)
        first = queue.claim("worker-a")
        assert first is not None and first.lease_id is not None
        retried = queue.fail(
            job_id, "worker-a", first.lease_id, RuntimeError("secret-api-key")
        )
        assert retried.status is JobStatus.PENDING
        assert retried.error_type == "RuntimeError"
        second = queue.claim("worker-b")
        assert second is not None and second.lease_id is not None
        failed = queue.fail(
            job_id, "worker-b", second.lease_id, KeyError("private-cookie")
        )
        assert failed.status is JobStatus.FAILED
        assert failed.error_type == "KeyError"

    raw = database.read_bytes()
    assert b"secret-api-key" not in raw and b"private-cookie" not in raw
    with sqlite3.connect(database) as db:
        columns = {row[1] for row in db.execute("PRAGMA table_info(narrative_jobs)")}
    forbidden = {"order", "side", "position", "entry_price", "exit_price", "pnl"}
    assert columns.isdisjoint(forbidden)


def test_source_identity_dedupes_refetches_but_rejects_content_conflicts(
    tmp_path: Path,
) -> None:
    clock = Clock()
    with _queue(tmp_path, clock) as queue:
        post_id = queue.enqueue(_post())
        assert queue.enqueue(
            replace(_post(), fetched_at=NOW + timedelta(seconds=30))
        ) == post_id
        with pytest.raises(JobContentConflict):
            queue.enqueue(replace(_post(), text="Different content under same tweet ID"))

        signal_id = queue.enqueue(_signal())
        refreshed = replace(
            _signal(),
            available_at=NOW + timedelta(seconds=5),
            provider_fdv_usd=Decimal("125000"),
            raw_context={"source": "debot", "refresh": 2},
        )
        assert queue.enqueue(refreshed) == signal_id
        with pytest.raises(JobContentConflict):
            queue.enqueue(replace(_signal(), token_symbol="OTHER"))
        assert queue.counts()[JobStatus.PENDING] == 2

        with pytest.raises(ValueError, match="max_attempts"):
            queue.enqueue(_post(), max_attempts=1.5)  # type: ignore[arg-type]


def test_lease_token_prevents_late_ack_from_same_worker_aba(tmp_path: Path) -> None:
    clock = Clock()
    with _queue(tmp_path, clock) as queue:
        job_id = queue.enqueue(_post(), max_attempts=3)
        old = queue.claim("same-worker", lease_seconds=5)
        assert old is not None and old.lease_id is not None
        clock.advance(6)
        current = queue.claim("same-worker", lease_seconds=5)
        assert current is not None and current.lease_id is not None
        assert current.lease_id != old.lease_id

        with pytest.raises(LeaseLostError):
            queue.ack(job_id, "same-worker", old.lease_id)
        with pytest.raises(LeaseLostError):
            queue.fail(job_id, "same-worker", old.lease_id, RuntimeError("late"))
        leased = queue.get(job_id)
        assert leased is not None and leased.lease_id == current.lease_id
        assert leased.status is JobStatus.LEASED
        assert queue.ack(job_id, "same-worker", current.lease_id).status is JobStatus.DONE
