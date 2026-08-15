"""Pure, conservative policy for promoting catalyst matches to mint alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from ..identity import utc_datetime
from .catalyst_mint import CatalystMintMatch
from .mint_qualification import (
    MINT_QUALIFIER_MODEL,
    MintQualification,
    MintQualificationAction,
)


STABILIZATION_SECONDS = 1.5
DECISION_DEADLINE_SECONDS = 15.0


class MintAlertAction(str, Enum):
    WAIT = "wait"
    ALERT = "alert"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class MintAlertPolicyDecision:
    action: MintAlertAction
    reason: str
    selected_match_id: str | None = None


def decide_mint_alert(
    matches: tuple[CatalystMintMatch, ...],
    *,
    now: datetime,
    qualifications: tuple[MintQualification, ...] = (),
) -> MintAlertPolicyDecision:
    """Require one exact CA and a timely Spark approval for one X post."""

    if not matches:
        raise ValueError("at least one catalyst mint match is required")
    tweet_ids = {item.catalyst_tweet_id for item in matches}
    if len(tweet_ids) != 1:
        raise ValueError("mint alert policy requires one catalyst tweet group")
    exact_cas = {item.exact_ca for item in matches}
    if len(exact_cas) > 1:
        return MintAlertPolicyDecision(
            MintAlertAction.REJECT, "one_tweet_multiple_exact_cas"
        )
    candidate = min(matches, key=lambda item: item.match_id)
    age = (
        utc_datetime(now) - utc_datetime(candidate.catalyst_created_at)
    ).total_seconds()
    if age > DECISION_DEADLINE_SECONDS:
        return MintAlertPolicyDecision(
            MintAlertAction.REJECT, "catalyst_alert_deadline_elapsed"
        )
    qualification = _qualification(candidate, qualifications)
    if qualification is not None:
        invalid = _invalid_qualification(candidate, qualification)
        if invalid is not None:
            return MintAlertPolicyDecision(MintAlertAction.REJECT, invalid)
        if qualification.action is MintQualificationAction.REJECT:
            return MintAlertPolicyDecision(
                MintAlertAction.REJECT, qualification.reason
            )
    if age < STABILIZATION_SECONDS:
        return MintAlertPolicyDecision(
            MintAlertAction.WAIT, "stabilizing_candidate_set"
        )
    if qualification is None:
        return MintAlertPolicyDecision(
            MintAlertAction.WAIT, "pending_spark_qualification"
        )
    return MintAlertPolicyDecision(
        MintAlertAction.ALERT,
        "spark_qualified_unique_catalyst_mint",
        candidate.match_id,
    )


def _qualification(
    candidate: CatalystMintMatch,
    qualifications: tuple[MintQualification, ...],
) -> MintQualification | None:
    matching = tuple(
        item for item in qualifications if item.match_id == candidate.match_id
    )
    if len(matching) > 1:
        raise ValueError("duplicate mint qualifications")
    return matching[0] if matching else None


def _invalid_qualification(
    candidate: CatalystMintMatch, qualification: MintQualification,
) -> str | None:
    if qualification.model != MINT_QUALIFIER_MODEL:
        return "unexpected_mint_qualifier_model"
    if qualification.started_at < candidate.observed_at:
        return "qualification_predates_complete_match"
    deadline = candidate.catalyst_created_at + timedelta(
        seconds=DECISION_DEADLINE_SECONDS
    )
    if qualification.completed_at > deadline:
        return "spark_qualification_late"
    return None


__all__ = [
    "DECISION_DEADLINE_SECONDS",
    "MintAlertAction",
    "MintAlertPolicyDecision",
    "STABILIZATION_SECONDS",
    "decide_mint_alert",
]
