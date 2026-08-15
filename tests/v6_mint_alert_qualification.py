"""Deterministic Spark qualification fixtures for mint-alert tests."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path

from debot4.v6.identity import utc_datetime
from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.mint_alert_gate import MintAlertGate, MintAlertVerdict
from debot4.v6.narrative.mint_qualification import (
    MINT_QUALIFIER_MODEL,
    MintQualification,
    MintQualificationAction,
)


def qualification(
    match: CatalystMintMatch,
    *,
    action: MintQualificationAction = MintQualificationAction.ALERT,
    completed_at: datetime | None = None,
    model: str = MINT_QUALIFIER_MODEL,
    reason: str | None = None,
) -> MintQualification:
    completed = utc_datetime(completed_at or match.observed_at)
    return MintQualification(
        match_id=match.match_id,
        action=action,
        started_at=match.observed_at,
        completed_at=completed,
        model=model,
        reason=reason or (
            "spark_alert"
            if action is MintQualificationAction.ALERT
            else "spark_reject"
        ),
    )


def approved_verdict(
    path: Path, match: CatalystMintMatch, *, now: datetime,
) -> MintAlertVerdict:
    gate = MintAlertGate(path, clock=lambda: now)
    gate.evaluate((match,))
    return gate.evaluate((), (qualification(match, completed_at=now),))[0]


class ApprovingMintAlertEvaluator:
    """Synchronous qualifier substitute for non-concurrency unit tests."""

    def __init__(self, path: Path, *, clock: Callable[[], datetime]) -> None:
        self.gate = MintAlertGate(path, clock=clock)
        self.clock = clock

    def evaluate(
        self, matches: Iterable[CatalystMintMatch],
    ) -> tuple[MintAlertVerdict, ...]:
        items = tuple(matches)
        self.gate.evaluate(items)
        evidence = tuple(
            qualification(item, completed_at=utc_datetime(self.clock()))
            for item in items
        )
        return self.gate.evaluate((), evidence)

    def snapshot(self) -> dict[str, object]:
        return self.gate.snapshot()

    def audit_snapshot(self) -> dict[str, object]:
        return self.gate.audit_snapshot()
