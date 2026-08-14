from __future__ import annotations

from datetime import timedelta
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from debot4.v6.debot.ranks_models import RankPage, RankSnapshot
from debot4.v6.debot.ranks_parser import parse_ranks
from debot4.v6.narrative.catalyst_mint_state import CatalystMintState
from debot4.v6.narrative.mint_monitor import NarrativeMintMonitor
from tests.v6_catalyst_mint_samples import (
    BBROKER_CA,
    BBROKER_MINT_AT,
    BBROKER_POST_AT,
    BBROKER_STATUS,
    FLAP_CA,
    FLAP_MINT_AT,
    FLAP_POST_AT,
    FLAP_STATUS,
    catalyst_post as _post,
    mint_snapshot as _mint,
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
        self.calls: list[str] = []

    def fetch(self, stage: str) -> RankPage:
        self.calls.append(stage)
        snapshot = replace(
            self.snapshot, stage=stage, launched=stage == "completed"
        )
        return RankPage(stage, (snapshot,), snapshot.fetched_at, 500)


def test_mint_monitor_self_throttles_without_delaying_due_results() -> None:
    timer = _Timer()
    client = _RanksClient(_mint())
    monitor = NarrativeMintMonitor(client, poll_seconds=1, timer=timer)
    accepted: list[tuple[RankSnapshot, ...]] = []

    assert monitor.poll_once(accepted.append) == (_mint(stage="new"),)
    timer.value = 0.99
    assert monitor.poll_once(accepted.append) == ()
    timer.value = 1.0
    assert monitor.poll_once(accepted.append) == (_mint(stage="completing"),)
    timer.value = 2.0
    assert monitor.poll_once(accepted.append) == (_mint(stage="completed"),)
    timer.value = 3.0
    assert monitor.poll_once(accepted.append) == (_mint(stage="new"),)
    assert client.calls == ["new", "completing", "completed", "new"]
    assert len(accepted) == 4
    assert monitor.snapshot() == {
        "poll_seconds": 1.0,
        "stages": ["new", "completing", "completed"],
        "full_cycle_seconds": 3.0,
        "last_stage": "new",
        "last_snapshot_count": 1,
        "last_stage_counts": {"new": 1, "completing": 1, "completed": 1},
    }


def test_state_keeps_latest_stage_without_losing_first_match_time(
    tmp_path: Path,
) -> None:
    state = CatalystMintState(
        tmp_path / "state.json",
        clock=lambda: BBROKER_MINT_AT + timedelta(minutes=1),
    )
    first_seen = BBROKER_MINT_AT + timedelta(seconds=1)
    state.observe_mints((_mint(stage="new", fetched_at=first_seen),))
    state.observe_mints((_mint(
        stage="completed", fetched_at=first_seen + timedelta(seconds=8)
    ),))

    (match,) = state.observe_posts((_post(),))

    assert match.token_stage == "completed"
    assert match.observed_at == first_seen
