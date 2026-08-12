"""Risk-state transitions that retain adverse history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..explosion import ExplosionCategory, ExplosionEvent


class RiskState(str, Enum):
    UNKNOWN = "unknown"
    DENIED = "denied"
    DISPUTED = "disputed"
    BLOCKED = "blocked"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class RiskObservation:
    subject: str
    actor_id: str
    actor_role: str
    state: RiskState
    reason: str
    occurred_at: datetime
    first_seen_at: datetime
    source_url: str
    evidence_hash: str
    chain: str = ""
    token_address: str = ""

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("risk observation requires a reason")
        object.__setattr__(self, "state", RiskState(self.state))


def risk_transition(
    previous: RiskObservation | None,
    current: RiskObservation,
) -> ExplosionEvent | None:
    if previous is None or previous.state == current.state:
        return None
    if previous.subject != current.subject:
        raise ValueError("risk observations refer to different subjects")
    subtype = (
        "risk_resolved"
        if current.state is RiskState.RESOLVED
        and previous.state in {RiskState.DENIED, RiskState.DISPUTED, RiskState.BLOCKED}
        else "risk_state_changed"
    )
    return ExplosionEvent(
        category=ExplosionCategory.RISK_RESOLUTION,
        subtype=subtype,
        occurred_at=current.occurred_at,
        first_seen_at=current.first_seen_at,
        subject=current.subject,
        actor_id=current.actor_id,
        actor_role=current.actor_role,
        source_url=current.source_url,
        evidence_hash=current.evidence_hash,
        previous={"state": previous.state.value, "reason": previous.reason},
        current={"state": current.state.value, "reason": current.reason},
        confidence="verified",
        chain=current.chain,
        token_address=current.token_address,
    )
