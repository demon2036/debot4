from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.mint_alert_gate import MintAlertGate
from debot4.v6.narrative.mint_alert_policy import MintAlertAction
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_OBSERVED_AT,
    BUDUJIN_POST_AT,
    BUDUJIN_RAW_CA,
    budujin_match,
    budujin_mint,
    budujin_post,
)


@pytest.mark.parametrize("stage", ("new", "completing", "completed"))
def test_all_debot_stages_can_alert_inside_deadline(
    tmp_path: Path, stage: str,
) -> None:
    match = replace(budujin_match(), token_stage=stage)
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    (verdict,) = gate.evaluate((match,))

    assert verdict.action is MintAlertAction.ALERT
    assert verdict.match.token_stage == stage
    assert verdict.reason == "verified_first_party_unique_catalyst_mint"


def test_pending_candidate_survives_restart_then_alerts(tmp_path: Path) -> None:
    now = [BUDUJIN_POST_AT + timedelta(seconds=5)]
    path = tmp_path / "gate.json"
    (waiting,) = MintAlertGate(path, clock=lambda: now[0]).evaluate(
        (budujin_match(),)
    )
    assert waiting.action is MintAlertAction.WAIT

    now[0] = BUDUJIN_POST_AT + timedelta(seconds=12)
    (alert,) = MintAlertGate(path, clock=lambda: now[0]).evaluate(
        (budujin_match(),)
    )
    assert alert.action is MintAlertAction.ALERT


def test_complete_candidate_after_deadline_is_rejected(tmp_path: Path) -> None:
    late = BUDUJIN_POST_AT + timedelta(seconds=15, microseconds=1)
    gate = MintAlertGate(tmp_path / "gate.json", clock=lambda: late)

    (verdict,) = gate.evaluate((budujin_match(),))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "catalyst_alert_deadline_elapsed"


def test_mint_created_before_x_post_is_never_an_alert(tmp_path: Path) -> None:
    snapshot = replace(
        budujin_mint(), created_at=BUDUJIN_POST_AT - timedelta(seconds=1)
    )
    match = CatalystMintMatch.from_observations(budujin_post(), snapshot)
    assert match is not None
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    (verdict,) = gate.evaluate((match,))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "mint_predates_catalyst"


def test_untrusted_author_rejects_at_deadline(tmp_path: Path) -> None:
    match = replace(budujin_match(), catalyst_author="randomcaller")
    at_deadline = BUDUJIN_POST_AT + timedelta(seconds=15)
    gate = MintAlertGate(tmp_path / "gate.json", clock=lambda: at_deadline)

    (verdict,) = gate.evaluate((match,))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "unverified_first_party_launch"


def test_missing_token_identity_rejects_at_deadline(tmp_path: Path) -> None:
    match = replace(budujin_match(), catalyst_text="Soon on Flap.sh")
    at_deadline = BUDUJIN_POST_AT + timedelta(seconds=15)
    gate = MintAlertGate(tmp_path / "gate.json", clock=lambda: at_deadline)

    (verdict,) = gate.evaluate((match,))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "token_identity_absent_from_catalyst"


def test_two_exact_cas_for_one_tweet_are_rejected(tmp_path: Path) -> None:
    second = CatalystMintMatch.from_observations(
        budujin_post(), budujin_mint(exact_ca=BUDUJIN_RAW_CA)
    )
    assert second is not None
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    verdicts = gate.evaluate((budujin_match(), second))

    assert {item.action for item in verdicts} == {MintAlertAction.REJECT}
    assert {item.reason for item in verdicts} == {"one_tweet_multiple_exact_cas"}


def test_later_conflict_invalidates_previously_selected_group(
    tmp_path: Path,
) -> None:
    now = [BUDUJIN_OBSERVED_AT]
    path = tmp_path / "gate.json"
    gate = MintAlertGate(path, clock=lambda: now[0])
    assert gate.evaluate((budujin_match(),))[0].action is MintAlertAction.ALERT
    second = CatalystMintMatch.from_observations(
        budujin_post(), budujin_mint(exact_ca=BUDUJIN_RAW_CA)
    )
    assert second is not None

    now[0] += timedelta(seconds=1)
    (verdict,) = gate.evaluate((second,))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "post_alert_multiple_exact_cas"
    group = gate.audit_snapshot()["candidate_groups"][0]
    assert group["outcome"] == "reject"
    assert group["reason"] == "post_alert_multiple_exact_cas"
