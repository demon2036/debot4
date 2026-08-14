from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3

from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.job_payloads import (
    ACTIVE_X_POST,
    PASSIVE_CATALYST_MINT,
    decode_job_input,
    encode_job_input,
)
from debot4.v6.narrative.job_priority import narrative_job_priority
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.worker import NarrativeResearchWorker
from debot4.v6.x.models import XPost


UTC = timezone.utc
POST_AT = datetime(2026, 8, 13, 13, 30, 41, tzinfo=UTC)
MINT_AT = datetime(2026, 8, 13, 13, 32, 2, tzinfo=UTC)
CA = "0xf1969f437fe3c485468fb17b0d9861c24dcd7777"
STATUS_ID = "2087894611733922300"
STATUS_URL = f"https://x.com/flapdotsh/status/{STATUS_ID}"


def _match() -> CatalystMintMatch:
    return CatalystMintMatch(
        exact_ca=CA,
        token_stage="new",
        token_created_at=MINT_AT,
        observed_at=MINT_AT + timedelta(seconds=1),
        token_name="bBroker",
        token_symbol="bBroker",
        provider_fdv_usd=Decimal("5000.67"),
        launchpad="flap",
        token_description=None,
        token_social_urls=(STATUS_URL, "https://availablepools.com"),
        token_status_url=STATUS_URL,
        catalyst_tweet_id=STATUS_ID,
        catalyst_author="flapdotsh",
        catalyst_text="Introducing the Flap bBroker Vault on BNB Chain.",
        catalyst_created_at=POST_AT,
        catalyst_fetched_at=POST_AT + timedelta(seconds=5),
    )


class _Runtime:
    def __init__(self) -> None:
        self.matches: list[CatalystMintMatch] = []

    def research_catalyst_mint(self, match: CatalystMintMatch) -> None:
        self.matches.append(match)

    def research_active_post(self, _post: object) -> None:
        raise AssertionError("wrong worker route")

    def research_telegram_post(self, _post: object) -> None:
        raise AssertionError("wrong worker route")

    def research_debot_signal(self, _signal: object, *, anomaly=None) -> None:
        raise AssertionError("wrong worker route")

    def research_market_anomaly(self, _anomaly: object) -> None:
        raise AssertionError("wrong worker route")


def test_bbroker_binding_round_trips_at_live_priority_and_worker_routes_it(
    tmp_path: Path,
) -> None:
    match = _match()
    job_id, kind, _digest, document = encode_job_input(match)
    decoded_kind, decoded = decode_job_input(document)

    assert kind == decoded_kind == PASSIVE_CATALYST_MINT
    assert decoded == match
    assert narrative_job_priority(match, now=match.observed_at) == 2
    assert narrative_job_priority(
        match, now=match.observed_at + timedelta(minutes=3)
    ) == 80

    runtime = _Runtime()
    with NarrativeJobQueue(
        tmp_path / "jobs.sqlite3", clock=lambda: match.observed_at
    ) as queue:
        assert queue.enqueue(match, priority=2) == job_id
        cycle = NarrativeResearchWorker(queue, runtime).work_once()
        assert cycle.status is JobStatus.DONE
        assert runtime.matches == [match]


def test_v3_queue_migration_preserves_existing_job_and_priority(
    tmp_path: Path,
) -> None:
    path = tmp_path / "jobs.sqlite3"
    post = XPost(
        "2087894611733922299",
        "flapdotsh",
        "existing queued catalyst",
        POST_AT,
        POST_AT + timedelta(seconds=1),
    )
    job_id, kind, digest, document = encode_job_input(post)
    assert kind == ACTIVE_X_POST
    stamp = POST_AT.isoformat()
    with sqlite3.connect(path) as database:
        database.executescript("""
            CREATE TABLE narrative_jobs (
                job_id TEXT PRIMARY KEY, kind TEXT NOT NULL,
                priority INTEGER NOT NULL, content_sha256 TEXT NOT NULL,
                payload_json TEXT NOT NULL, status TEXT NOT NULL,
                attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
                available_at TEXT NOT NULL, lease_owner TEXT, lease_id TEXT,
                lease_expires_at TEXT, error_type TEXT, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, completed_at TEXT
            );
            PRAGMA user_version=3;
        """)
        database.execute(
            "INSERT INTO narrative_jobs VALUES (?,?,?,?,?,'pending',0,3,?,"
            "NULL,NULL,NULL,NULL,?,?,NULL)",
            (job_id, kind, 7, digest, document, stamp, stamp, stamp),
        )

    with NarrativeJobQueue(path, clock=lambda: MINT_AT) as queue:
        migrated = queue.get(job_id)
        assert migrated is not None
        assert migrated.payload == post
        assert migrated.priority == 7
        assert queue.enqueue(_match(), priority=2)

    with sqlite3.connect(path) as database:
        assert database.execute("PRAGMA user_version").fetchone()[0] == 4
