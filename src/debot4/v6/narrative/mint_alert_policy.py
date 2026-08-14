"""Pure, conservative policy for promoting catalyst matches to mint alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from ..identity import utc_datetime
from .catalyst_mint import CatalystMintMatch


STABILIZATION_SECONDS = 12.0
DECISION_DEADLINE_SECONDS = 15.0
_FIRST_PARTY_AUTHORS = {
    "flap": frozenset({"flapdotsh"}),
    "flap_stocks_vault": frozenset({"flapdotsh"}),
    "four_meme": frozenset({"fourdotmemezh"}),
    "four_meme_agent": frozenset({"fourdotmemezh"}),
}


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
    matches: tuple[CatalystMintMatch, ...], *, now: datetime,
) -> MintAlertPolicyDecision:
    """Decide one tweet group without network, model, or market-price input."""

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
    if age < STABILIZATION_SECONDS:
        return MintAlertPolicyDecision(
            MintAlertAction.WAIT, "stabilizing_candidate_set"
        )
    if age > DECISION_DEADLINE_SECONDS:
        return MintAlertPolicyDecision(
            MintAlertAction.REJECT, "catalyst_alert_deadline_elapsed"
        )
    if candidate.mint_delay_seconds < 0:
        return MintAlertPolicyDecision(
            MintAlertAction.REJECT, "mint_predates_catalyst"
        )
    if not is_first_party_launch(candidate):
        return _wait_or_reject(age, "unverified_first_party_launch")
    if not token_identity_is_named(candidate):
        return _wait_or_reject(age, "token_identity_absent_from_catalyst")
    return MintAlertPolicyDecision(
        MintAlertAction.ALERT,
        "verified_first_party_unique_catalyst_mint",
        candidate.match_id,
    )


def is_first_party_launch(match: CatalystMintMatch) -> bool:
    launchpad = _key(match.launchpad)
    return match.catalyst_author.casefold() in _FIRST_PARTY_AUTHORS.get(
        launchpad, ()
    )


def token_identity_is_named(match: CatalystMintMatch) -> bool:
    text = _identity_text(match.catalyst_text)
    candidates = (match.token_name, match.token_symbol)
    return any(
        len(identity) >= 2 and identity in text
        for raw in candidates
        if (identity := _identity_text(raw or ""))
    )


def _wait_or_reject(age: float, reason: str) -> MintAlertPolicyDecision:
    if age < DECISION_DEADLINE_SECONDS:
        return MintAlertPolicyDecision(MintAlertAction.WAIT, f"pending_{reason}")
    return MintAlertPolicyDecision(MintAlertAction.REJECT, reason)


def _key(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (value or "").casefold()).strip("_")


def _identity_text(value: str) -> str:
    return re.sub(r"[\W_]+", "", value.casefold(), flags=re.UNICODE)


__all__ = [
    "DECISION_DEADLINE_SECONDS",
    "MintAlertAction",
    "MintAlertPolicyDecision",
    "STABILIZATION_SECONDS",
    "decide_mint_alert",
    "is_first_party_launch",
    "token_identity_is_named",
]
