from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.debot.ranks_parser import parse_ranks
from debot4.v6.debot.ranks_state import RankState


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, 0, tzinfo=UTC)
TOKEN = "0x" + "a" * 40


def _payload(kols: int = 2) -> dict[str, object]:
    return {
        "code": 0,
        "data": {
            "new_creations": [{
                "chain": "bsc",
                "contract": TOKEN,
                "meta": {"name": "Story Dog", "symbol": "DOG"},
                "meme_tag_stats": {
                    "kols": str(kols),
                    "kolsHolds": "123.45",
                    "lastPrice": "0.0001",
                    "totalSupply": "1000000000",
                    "progress": "0.5",
                },
                "kol_list": ["alpha", {"alias": "beta"}],
            }],
            "completing": [],
            "completed": [],
        },
    }


def test_ranks_parser_keeps_exact_kol_snapshot() -> None:
    rows = parse_ranks(_payload(), "new", NOW)
    assert len(rows) == 1
    assert rows[0].token_address == TOKEN
    assert rows[0].kols == 2
    assert rows[0].kol_aliases == ("alpha", "beta")
    assert rows[0].provider_fdv_usd == Decimal("100000")
    assert rows[0].launched is False


def test_rank_state_only_emits_a_positive_change_and_survives_restart(tmp_path) -> None:
    path = tmp_path / "ranks.json"
    state = RankState(path)
    initial = RankSnapshot(
        TOKEN, "new", NOW, "Story Dog", "DOG", 2, ("alpha",),
        Decimal("10"), Decimal("100000"), False,
    )
    assert state.observe(initial) is None
    state.save()
    restored = RankState(path)
    increase = restored.observe(RankSnapshot(
        TOKEN, "completing", NOW + timedelta(seconds=2), "Story Dog", "DOG",
        4, ("alpha", "beta"), Decimal("15"), Decimal("120000"), False,
    ))
    assert increase is not None
    assert increase.previous_kols == 2
    assert increase.increase == 2
