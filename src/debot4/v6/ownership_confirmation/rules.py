"""Pure state transitions for creator and IP-holder confirmation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from ..explosion import ExplosionCategory, ExplosionEvent


_EVM_CA = re.compile(r"0x[a-f0-9]{40}")


class OwnershipState(str, Enum):
    UNKNOWN = "unknown"
    DENIED = "denied"
    ACKNOWLEDGED = "acknowledged"
    CA_BOUND = "ca_bound"


@dataclass(frozen=True, slots=True)
class OwnershipObservation:
    subject: str
    actor_id: str
    actor_role: str
    state: OwnershipState
    occurred_at: datetime
    first_seen_at: datetime
    source_url: str
    evidence_hash: str
    chain: str = ""
    token_address: str = ""

    def __post_init__(self) -> None:
        state = OwnershipState(self.state)
        address = self.token_address.strip().casefold()
        if state is OwnershipState.CA_BOUND and not _EVM_CA.fullmatch(address):
            raise ValueError("CA-bound ownership requires an exact EVM address")
        if state is not OwnershipState.CA_BOUND and address:
            raise ValueError("only CA-bound ownership may carry an address")
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "token_address", address)


def ownership_transition(
    previous: OwnershipObservation | None,
    current: OwnershipObservation,
) -> ExplosionEvent | None:
    if previous is None or previous.state is current.state and (
        previous.token_address == current.token_address
    ):
        return None
    if previous.subject != current.subject or previous.actor_id != current.actor_id:
        raise ValueError("ownership observations refer to different identities")
    return ExplosionEvent(
        category=ExplosionCategory.OWNERSHIP_CONFIRMATION,
        subtype=f"{previous.state.value}_to_{current.state.value}",
        occurred_at=current.occurred_at,
        first_seen_at=current.first_seen_at,
        subject=current.subject,
        actor_id=current.actor_id,
        actor_role=current.actor_role,
        source_url=current.source_url,
        evidence_hash=current.evidence_hash,
        previous={"state": previous.state.value, "token_address": previous.token_address},
        current={"state": current.state.value, "token_address": current.token_address},
        confidence="verified",
        chain=current.chain,
        token_address=current.token_address,
    )
