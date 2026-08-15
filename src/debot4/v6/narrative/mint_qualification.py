"""Domain contract for semantic qualification of an exact catalyst mint."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol, TYPE_CHECKING

from ..identity import utc_datetime
from .catalyst_mint import CatalystMintMatch

if TYPE_CHECKING:
    from .mint_alert_gate import MintAlertVerdict


MINT_QUALIFIER_MODEL = "gpt-5.3-codex-spark"


class MintQualificationAction(str, Enum):
    ALERT = "alert"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class MintQualification:
    match_id: str
    action: MintQualificationAction
    started_at: datetime
    completed_at: datetime
    model: str
    reason: str

    def __post_init__(self) -> None:
        started = utc_datetime(self.started_at)
        completed = utc_datetime(self.completed_at)
        if not self.match_id.strip():
            raise ValueError("mint qualification match id is required")
        if completed < started:
            raise ValueError("mint qualification completes before it starts")
        if not self.model.strip() or not self.reason.strip():
            raise ValueError("mint qualification provenance is required")
        object.__setattr__(self, "started_at", started)
        object.__setattr__(self, "completed_at", completed)

    @property
    def latency_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()


class MintQualifier(Protocol):
    def qualify(self, match: CatalystMintMatch) -> MintQualification: ...


class MintAlertEvaluator(Protocol):
    def evaluate(
        self, matches: Iterable[CatalystMintMatch],
    ) -> tuple["MintAlertVerdict", ...]: ...

    def snapshot(self) -> dict[str, object]: ...

    def audit_snapshot(self) -> dict[str, object]: ...


def qualification_payload(item: MintQualification) -> dict[str, object]:
    return {
        "match_id": item.match_id,
        "action": item.action.value,
        "started_at": item.started_at.isoformat(),
        "completed_at": item.completed_at.isoformat(),
        "model": item.model,
        "reason": item.reason,
    }


def qualification_from_payload(raw: object) -> MintQualification:
    if not isinstance(raw, dict) or set(raw) != {
        "match_id", "action", "started_at", "completed_at", "model", "reason",
    }:
        raise ValueError("invalid mint qualification structure")
    return MintQualification(
        match_id=str(raw["match_id"]),
        action=MintQualificationAction(str(raw["action"])),
        started_at=datetime.fromisoformat(str(raw["started_at"])),
        completed_at=datetime.fromisoformat(str(raw["completed_at"])),
        model=str(raw["model"]),
        reason=str(raw["reason"]),
    )


__all__ = [
    "MINT_QUALIFIER_MODEL",
    "MintAlertEvaluator",
    "MintQualification",
    "MintQualificationAction",
    "MintQualifier",
    "qualification_from_payload",
    "qualification_payload",
]
