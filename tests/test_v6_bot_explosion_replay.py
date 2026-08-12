from pathlib import Path

import pytest

from debot4.v6.explosion import load_replay


CASE = Path(__file__).resolve().parents[1] / "research/golden_dogs/cases/bot_2026_08.json"


def test_bot_replay_keeps_two_distinct_market_waves() -> None:
    replay = load_replay(CASE)

    assert replay.token_address == "0xbcad9b1b85af1cd81437252bf50b87235c0b7777"
    assert [wave.kind for wave in replay.waves] == ["initial_launch", "secondary_catalyst"]
    assert replay.waves[0].peak_multiple == pytest.approx(517.6841630998)
    assert replay.waves[1].peak_multiple == pytest.approx(3.621444477)


def test_bot_second_wave_preserves_causal_timing() -> None:
    replay = load_replay(CASE)
    moments = {item.label: item for item in replay.waves[1].moments}

    assert moments["bot_avatar_resource_created"].offset_from_move_seconds == -0.042
    assert moments["bot_banner_resource_created"].offset_from_move_seconds == 51
    assert moments["official_grok_bot_announcement"].offset_from_move_seconds == 1325
    assert moments["official_grok_bot_announcement"].occurred_at > replay.waves[1].peak_at


def test_bot_candidates_are_not_silently_promoted() -> None:
    replay = load_replay(CASE)

    assert all(item.status != "active_verified" for item in replay.candidates)
    assert any(item.kind == "competing_ca" for item in replay.candidates)
    assert any("executable" in item.casefold() for item in replay.limitations)


def test_bot_first_wave_separates_early_ca_selection_from_origin() -> None:
    replay = load_replay(CASE)
    moments = {item.label: item for item in replay.waves[0].moments}
    candidates = {item.subject: item for item in replay.candidates}

    assert moments["false2z_selects_main_ca"].offset_from_move_seconds == 165
    assert moments["9999btcname_position_post"].offset_from_move_seconds == 740
    assert candidates["@false2z"].kind == "canonical_ca_amplifier"
    assert candidates["@false2z"].status == "research_candidate"
