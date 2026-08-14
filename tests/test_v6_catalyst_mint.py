from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from debot4.v6.debot.ranks_models import RankPage, RankSnapshot
from debot4.v6.debot.ranks_parser import parse_ranks
from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.collection import NarrativeCollector
from debot4.v6.narrative.job_payloads import encode_job_input
from debot4.v6.narrative.job_queue import JobStatus, NarrativeJobQueue
from debot4.v6.narrative.live_signal_filter import BscRealtimeSignalFilter
from debot4.v6.narrative.mint_monitor import NarrativeMintMonitor
from debot4.v6.x.models import XPost


UTC = timezone.utc
BBROKER_CA = "0xf1969f437fe3c485468fb17b0d9861c24dcd7777"
BBROKER_STATUS = "2087894611733922300"
BBROKER_POST_AT = datetime(2026, 8, 13, 13, 30, 41, tzinfo=UTC)
BBROKER_MINT_AT = datetime(2026, 8, 13, 13, 32, 2, tzinfo=UTC)
FLAP_CA = "0x6d2137fe9113d28135edfb274cb0d94447497777"
FLAP_STATUS = "2088104486892138899"
FLAP_POST_AT = datetime(2026, 8, 14, 3, 24, 39, tzinfo=UTC)
FLAP_MINT_AT = datetime(2026, 8, 14, 3, 24, 55, tzinfo=UTC)


def _post(
    status_id: str = BBROKER_STATUS,
    created_at: datetime = BBROKER_POST_AT,
    fetched_at: datetime | None = None,
) -> XPost:
    return XPost(
        status_id,
        "flapdotsh",
        "Introducing the Flap bBroker Vault on BNB Chain, powered by bStocks.",
        created_at,
        fetched_at or created_at + timedelta(seconds=5),
    )


def _mint(
    *,
    exact_ca: str = BBROKER_CA,
    status_id: str = BBROKER_STATUS,
    created_at: datetime = BBROKER_MINT_AT,
    fetched_at: datetime | None = None,
    social_urls: tuple[str, ...] | None = None,
) -> RankSnapshot:
    urls = social_urls or (
        f"https://x.com/flapdotsh/status/{status_id}",
        "https://availablepools.com",
    )
    return RankSnapshot(
        exact_ca,
        "new",
        fetched_at or created_at + timedelta(seconds=1),
        "bBroker",
        "bBroker",
        0,
        (),
        Decimal("0"),
        Decimal("5000.67"),
        False,
        created_at,
        "flap",
        None,
        urls,
    )


def test_real_bbroker_rank_shape_keeps_creation_and_exact_status_metadata() -> None:
    payload = {
        "code": 0,
        "data": {
            "new_creations": [{
                "chain": "bsc",
                "contract": BBROKER_CA,
                "status": 0,
                "meta": {
                    "name": "bBroker",
                    "symbol": "bBroker",
                    "launchpad": "flap",
                    "create_time": int(BBROKER_MINT_AT.timestamp() * 1_000),
                },
                "meme_tag_stats": {
                    "kols": "0",
                    "lastPrice": "0.00000500067",
                    "totalSupply": "1000000000",
                    "progress": "0.01",
                },
                "social_info": {
                    "twitter": (
                        "https://x.com/flapdotsh/status/2087894611733922300"
                    ),
                    "website": "https://availablepools.com",
                },
            }],
            "completing": [],
            "completed": [],
        },
    }

    (snapshot,) = parse_ranks(payload, "new", BBROKER_MINT_AT + timedelta(seconds=1))

    assert snapshot.token_address == BBROKER_CA
    assert snapshot.created_at == BBROKER_MINT_AT
    assert snapshot.launchpad == "flap"
    assert snapshot.provider_fdv_usd == Decimal("5000.67000000000")
    assert snapshot.social_urls == (
        "https://x.com/flapdotsh/status/2087894611733922300",
        "https://availablepools.com",
    )


def test_bbroker_matches_when_mint_arrives_before_post_and_survives_restart(
    tmp_path: Path,
) -> None:
    path = tmp_path / "private" / "catalyst-mints.json"
    clock = lambda: BBROKER_MINT_AT + timedelta(minutes=1)
    state = CatalystMintState(path, clock=clock)

    assert state.observe_mints((_mint(),)) == ()
    (match,) = state.observe_posts((_post(),))

    assert match.exact_ca == BBROKER_CA
    assert match.catalyst_tweet_id == BBROKER_STATUS
    assert match.mint_delay_seconds == 81
    assert match.observed_at == BBROKER_MINT_AT + timedelta(seconds=1)
    restarted = CatalystMintState(path, clock=clock)
    assert restarted.observe_posts(()) == (match,)
    restarted.acknowledge((match.match_id,))
    assert CatalystMintState(path, clock=clock).observe_mints(()) == ()


def test_flap_dividend_post_matches_when_post_arrives_before_mint(
    tmp_path: Path,
) -> None:
    clock = lambda: FLAP_MINT_AT + timedelta(minutes=1)
    state = CatalystMintState(tmp_path / "state.json", clock=clock)
    post = _post(
        FLAP_STATUS,
        FLAP_POST_AT,
        FLAP_POST_AT + timedelta(seconds=7, microseconds=689_922),
    )
    mint = _mint(
        exact_ca=FLAP_CA,
        status_id=FLAP_STATUS,
        created_at=FLAP_MINT_AT,
        fetched_at=FLAP_MINT_AT + timedelta(seconds=1),
    )

    assert state.observe_posts((post,)) == ()
    (match,) = state.observe_mints((mint,))

    assert match.exact_ca == FLAP_CA
    assert match.mint_delay_seconds == 16
    assert match.catalyst_fetched_at == post.fetched_at


def test_only_exact_status_id_inside_time_window_can_match(tmp_path: Path) -> None:
    clock = lambda: BBROKER_POST_AT + timedelta(minutes=14)
    state = CatalystMintState(tmp_path / "state.json", clock=clock)
    assert state.observe_posts((_post(),)) == ()

    profile_only = _mint(social_urls=("https://x.com/flapdotsh",))
    late = _mint(created_at=BBROKER_POST_AT + timedelta(minutes=11))

    assert state.observe_mints((profile_only, late)) == ()


class _Timer:
    value = 0.0

    def __call__(self) -> float:
        return self.value


class _RanksClient:
    def __init__(self, snapshot: RankSnapshot) -> None:
        self.snapshot = snapshot
        self.calls = 0

    def fetch(self, stage: str) -> RankPage:
        assert stage == "new"
        self.calls += 1
        return RankPage(stage, (self.snapshot,), self.snapshot.fetched_at, 500)


def test_mint_monitor_self_throttles_without_delaying_due_results() -> None:
    timer = _Timer()
    client = _RanksClient(_mint())
    monitor = NarrativeMintMonitor(client, poll_seconds=1, timer=timer)
    accepted: list[tuple[RankSnapshot, ...]] = []

    assert monitor.poll_once(accepted.append) == (_mint(),)
    timer.value = 0.99
    assert monitor.poll_once(accepted.append) == ()
    timer.value = 1.0
    assert monitor.poll_once(accepted.append) == (_mint(),)
    assert client.calls == 2 and len(accepted) == 2


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
    post, mint = _post(), _mint()
    observed_at = mint.fetched_at
    state = CatalystMintState(
        tmp_path / "join.json", clock=lambda: observed_at
    )
    with NarrativeJobQueue(
        tmp_path / "jobs.sqlite3", clock=lambda: observed_at
    ) as queue:
        collector = NarrativeCollector(
            _XSource(post),
            object(),
            object(),
            queue,
            mint_monitor=_MintSource(mint),
            catalyst_mints=state,
            clock=lambda: observed_at,
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
        assert collector.filter_snapshot()["reasons"] == {
            "exact_catalyst_mint_binding": 1,
            "reviewed_catalyst_event": 1,
        }
