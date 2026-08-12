"""Distribution-entry state machine with separate announcement and availability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum

from ..explosion import ExplosionCategory, ExplosionEvent


class AccessState(IntEnum):
    ABSENT = 0
    ANNOUNCED = 1
    DISCOVERABLE = 2
    DEPOSIT_OPEN = 3
    TRADING_OPEN = 4


@dataclass(frozen=True, slots=True)
class AccessObservation:
    venue: str
    market: str
    actor_id: str
    actor_role: str
    state: AccessState
    occurred_at: datetime
    first_seen_at: datetime
    source_url: str
    evidence_hash: str
    chain: str = ""
    token_address: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "state", AccessState(self.state))


def access_transition(
    previous: AccessObservation | None,
    current: AccessObservation,
) -> ExplosionEvent | None:
    if previous is None or previous.state == current.state:
        return None
    if previous.venue != current.venue or previous.market != current.market:
        raise ValueError("distribution observations refer to different markets")
    subtype = (
        "distribution_opened"
        if current.state > previous.state
        else "distribution_withdrawn"
    )
    return ExplosionEvent(
        category=ExplosionCategory.DISTRIBUTION_ACCESS,
        subtype=subtype,
        occurred_at=current.occurred_at,
        first_seen_at=current.first_seen_at,
        subject=f"{current.venue}:{current.market}",
        actor_id=current.actor_id,
        actor_role=current.actor_role,
        source_url=current.source_url,
        evidence_hash=current.evidence_hash,
        previous={"state": previous.state.name.casefold()},
        current={"state": current.state.name.casefold()},
        confidence="verified",
        chain=current.chain,
        token_address=current.token_address,
    )
