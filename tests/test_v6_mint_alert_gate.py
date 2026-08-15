from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.mint_alert_gate import MintAlertGate
from debot4.v6.narrative.mint_alert_policy import MintAlertAction
from debot4.v6.narrative.mint_qualification import MintQualificationAction
from tests.v6_catalyst_mint_samples import (
    BUDUJIN_OBSERVED_AT,
    BUDUJIN_POST_AT,
    BUDUJIN_RAW_CA,
    budujin_match,
    budujin_mint,
    budujin_post,
)
from tests.v6_mint_alert_qualification import qualification


@pytest.mark.parametrize("stage", ("new", "completing", "completed"))
def test_all_debot_stages_require_spark_then_alert_inside_deadline(
    tmp_path: Path, stage: str,
) -> None:
    match = replace(budujin_match(), token_stage=stage)
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    (waiting,) = gate.evaluate((match,))
    (alert,) = gate.evaluate((), (qualification(match),))

    assert waiting.action is MintAlertAction.WAIT
    assert waiting.reason == "pending_spark_qualification"
    assert alert.action is MintAlertAction.ALERT
    assert alert.match.token_stage == stage
    assert alert.reason == "spark_qualified_unique_catalyst_mint"
    assert alert.qualification is not None


def test_pending_candidate_survives_restart_then_alerts(tmp_path: Path) -> None:
    path = tmp_path / "gate.json"
    (waiting,) = MintAlertGate(
        path, clock=lambda: BUDUJIN_OBSERVED_AT
    ).evaluate((budujin_match(),))
    assert waiting.action is MintAlertAction.WAIT

    (alert,) = MintAlertGate(
        path, clock=lambda: BUDUJIN_OBSERVED_AT
    ).evaluate((), (qualification(budujin_match()),))

    assert alert.action is MintAlertAction.ALERT
    assert alert.qualification is not None


def test_candidate_after_deadline_is_rejected(tmp_path: Path) -> None:
    late = BUDUJIN_POST_AT + timedelta(seconds=15, microseconds=1)
    gate = MintAlertGate(tmp_path / "gate.json", clock=lambda: late)

    (verdict,) = gate.evaluate((budujin_match(),))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "catalyst_alert_deadline_elapsed"


def test_preparing_mint_may_precede_x_post_then_alert(tmp_path: Path) -> None:
    snapshot = replace(
        budujin_mint(), created_at=BUDUJIN_POST_AT - timedelta(seconds=1)
    )
    match = CatalystMintMatch.from_observations(budujin_post(), snapshot)
    assert match is not None
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    gate.evaluate((match,))
    (verdict,) = gate.evaluate((), (qualification(match),))

    assert verdict.action is MintAlertAction.ALERT


def test_spark_rejection_is_terminal_for_any_author(tmp_path: Path) -> None:
    match = replace(budujin_match(), catalyst_author="randomcaller")
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    gate.evaluate((match,))
    (verdict,) = gate.evaluate((), (qualification(
        match, action=MintQualificationAction.REJECT,
    ),))

    assert verdict.action is MintAlertAction.REJECT
    assert verdict.reason == "spark_reject"


def test_spark_approval_can_use_metadata_when_post_omits_token_name(
    tmp_path: Path,
) -> None:
    match = replace(budujin_match(), catalyst_text="Soon on Flap.sh")
    gate = MintAlertGate(
        tmp_path / "gate.json", clock=lambda: BUDUJIN_OBSERVED_AT
    )

    gate.evaluate((match,))
    (verdict,) = gate.evaluate((), (qualification(match),))

    assert verdict.action is MintAlertAction.ALERT


def test_wrong_model_or_late_spark_evidence_is_rejected(tmp_path: Path) -> None:
    for name, evidence, reason in (
        (
            "model",
            qualification(budujin_match(), model="gpt-5.3-codex"),
            "unexpected_mint_qualifier_model",
        ),
        (
            "late",
            qualification(
                budujin_match(),
                completed_at=BUDUJIN_POST_AT + timedelta(seconds=15, microseconds=1),
            ),
            "spark_qualification_late",
        ),
    ):
        gate = MintAlertGate(
            tmp_path / f"{name}.json", clock=lambda: BUDUJIN_OBSERVED_AT
        )
        gate.evaluate((budujin_match(),))
        (verdict,) = gate.evaluate((), (evidence,))
        assert verdict.action is MintAlertAction.REJECT
        assert verdict.reason == reason


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
    gate = MintAlertGate(tmp_path / "gate.json", clock=lambda: now[0])
    match = budujin_match()
    gate.evaluate((match,))
    assert gate.evaluate((), (qualification(match),))[0].action is (
        MintAlertAction.ALERT
    )
    second = CatalystMintMatch.from_observations(
        budujin_post(), budujin_mint(exact_ca=BUDUJIN_RAW_CA)
    )
    assert second is not None

    now[0] += timedelta(seconds=1)
    verdicts = gate.evaluate((second,))

    assert {item.action for item in verdicts} == {MintAlertAction.REJECT}
    assert {item.reason for item in verdicts} == {
        "post_alert_multiple_exact_cas",
    }
    group = gate.audit_snapshot()["candidate_groups"][0]
    assert group["outcome"] == "reject"
    assert group["reason"] == "post_alert_multiple_exact_cas"
