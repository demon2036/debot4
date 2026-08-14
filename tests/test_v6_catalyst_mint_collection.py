from __future__ import annotations

from pathlib import Path

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.collection import NarrativeCollector
from debot4.v6.narrative.job_payloads import encode_job_input
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.live_signal_filter import BscRealtimeSignalFilter
from debot4.v6.narrative.mint_location_store import MintLocationStore
from debot4.v6.x.models import XPost
from tests.v6_catalyst_mint_samples import (
    BBROKER_POST_AT,
    BBROKER_STATUS,
    catalyst_post,
    mint_snapshot,
)


class _XSource:
    def __init__(self, post: XPost) -> None:
        self.post = post

    def monitor_once(self, accept=None) -> tuple[XPost, ...]:
        posts = (self.post,)
        if accept is not None:
            accept(posts)
        return posts


class _MintSource:
    def __init__(self, mint: RankSnapshot) -> None:
        self.mint = mint

    def poll_once(self, accept=None) -> tuple[RankSnapshot, ...]:
        snapshots = (self.mint,)
        if accept is not None:
            accept(snapshots)
        return snapshots


def test_collector_turns_no_ca_bbroker_post_into_exact_ca_job(
    tmp_path: Path,
) -> None:
    post, mint = catalyst_post(), mint_snapshot()
    observed_at = mint.fetched_at
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: observed_at
    )
    with (
        NarrativeJobQueue(
            tmp_path / "jobs.sqlite3", clock=lambda: observed_at
        ) as queue,
        MintLocationStore(
            tmp_path / "mint.sqlite3", clock=lambda: observed_at
        ) as locations,
    ):
        collector = NarrativeCollector(
            _XSource(post), object(), object(), queue,
            mint_monitor=_MintSource(mint), catalyst_mints=state,
            mint_locations=locations, clock=lambda: observed_at,
            signal_filter=BscRealtimeSignalFilter(clock=lambda: observed_at),
        )

        assert collector.collect_x_once() == (post,)
        (match,) = collector.collect_mints_once()

        match_job_id = encode_job_input(match)[0]
        queued = queue.get(match_job_id)
        assert queued is not None
        assert queued.kind == "passive_catalyst_mint"
        assert queued.priority == 2
        assert queue.counts()[JobStatus.PENDING] == 2
        assert collector.mint_pipeline_snapshot()["mint_locations"] == {
            "configured": True,
            **locations.snapshot(),
        }
        assert collector.filter_snapshot()["reasons"] == {
            "exact_catalyst_mint_binding": 1,
            "reviewed_catalyst_event": 1,
        }


def test_no_social_mint_is_located_without_queueing_grok(tmp_path: Path) -> None:
    mint = mint_snapshot(social_urls=("https://availablepools.com",))
    with (
        NarrativeJobQueue(tmp_path / "jobs.sqlite3") as queue,
        MintLocationStore(tmp_path / "mint.sqlite3") as locations,
    ):
        collector = NarrativeCollector(
            object(), object(), object(), queue,
            mint_monitor=_MintSource(mint), mint_locations=locations,
        )

        assert collector.collect_mints_once() == ()
        assert locations.snapshot()["unique_exact_cas"] == 1
        assert queue.counts()[JobStatus.PENDING] == 0
        pipeline = collector.mint_pipeline_snapshot()
        assert pipeline["hard_catalyst_bindings_queued"] == 0
        assert pipeline["raw_location_queues_research"] is False


def test_routine_post_stays_available_for_later_exact_mint_binding(
    tmp_path: Path,
) -> None:
    post = XPost(
        BBROKER_STATUS, "GCsheng", "早安", BBROKER_POST_AT,
        BBROKER_POST_AT,
    )
    mint = mint_snapshot(social_urls=(
        f"https://x.com/GCsheng/status/{BBROKER_STATUS}",
    ))
    observed_at = mint.fetched_at
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: observed_at,
    )
    with (
        NarrativeJobQueue(
            tmp_path / "jobs.sqlite3", clock=lambda: observed_at,
        ) as queue,
        MintLocationStore(
            tmp_path / "mint.sqlite3", clock=lambda: observed_at,
        ) as locations,
    ):
        collector = NarrativeCollector(
            _XSource(post), object(), object(), queue,
            mint_monitor=_MintSource(mint), catalyst_mints=state,
            mint_locations=locations, clock=lambda: observed_at,
            signal_filter=BscRealtimeSignalFilter(clock=lambda: observed_at),
        )

        collector.collect_x_once()
        assert queue.counts()[JobStatus.PENDING] == 0
        (match,) = collector.collect_mints_once()

        assert match.exact_ca == mint.token_address
        assert queue.counts()[JobStatus.PENDING] == 1
        assert collector.filter_snapshot()["reasons"] == {
            "exact_catalyst_mint_binding": 1,
            "routine_x_chatter": 1,
        }
