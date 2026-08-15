"""Durable per-tweet gate between exact metadata matches and mint alerts."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import RLock

from ..identity import utc_datetime, utc_now
from .catalyst_mint import CatalystMintMatch
from .catalyst_mint_payload import catalyst_mint_payload
from .mint_alert_gate_codec import (
    GATE_SCHEMA,
    MintAlertGateGroup,
    MintAlertGateState,
    MintAlertGateStateError,
    read_mint_alert_gate_state,
    write_mint_alert_gate_state,
)
from .mint_alert_policy import MintAlertAction, decide_mint_alert
from .mint_qualification import (
    MintQualification,
    MintQualificationAction,
    qualification_payload,
)


MintAlertGateError = MintAlertGateStateError


@dataclass(frozen=True, slots=True)
class MintAlertVerdict:
    match: CatalystMintMatch
    action: MintAlertAction
    reason: str
    qualification: MintQualification | None = None


@dataclass(slots=True)
class _Group:
    tweet_id: str
    matches: dict[str, CatalystMintMatch]
    outcome: str
    reason: str
    selected_match_id: str | None
    qualification: MintQualification | None
    updated_at: datetime


class MintAlertGate:
    """Remember candidate conflicts and terminal decisions across restarts."""

    def __init__(
        self,
        path: str | Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        retention: timedelta = timedelta(days=1),
        max_groups: int = 2_048,
    ) -> None:
        if not timedelta(hours=1) <= retention <= timedelta(days=7):
            raise ValueError("mint alert gate retention must be 1 hour to 7 days")
        if isinstance(max_groups, bool) or not 100 <= max_groups <= 20_000:
            raise ValueError("mint alert gate group limit is invalid")
        self.path = Path(path)
        self.clock = clock
        self.retention = retention
        self.max_groups = max_groups
        self._lock = RLock()
        loaded = read_mint_alert_gate_state(self.path, max_groups=max_groups)
        if loaded is None:
            self.policy_started_at = self._now()
            self._groups: dict[str, _Group] = {}
            self._write()
        else:
            self.policy_started_at = loaded.policy_started_at
            self._groups = {
                item.tweet_id: _Group(
                    item.tweet_id,
                    {match.match_id: match for match in item.matches},
                    item.outcome,
                    item.reason,
                    item.selected_match_id,
                    item.qualification,
                    item.updated_at,
                )
                for item in loaded.groups
            }

    def evaluate(
        self,
        matches: Iterable[CatalystMintMatch],
        qualifications: Iterable[MintQualification] = (),
    ) -> tuple[MintAlertVerdict, ...]:
        items = tuple(matches)
        evidence = tuple(qualifications)
        if len(items) > 1_000:
            raise ValueError("too many mint candidates in one gate evaluation")
        if any(not isinstance(item, CatalystMintMatch) for item in items):
            raise TypeError("mint alert gate requires CatalystMintMatch evidence")
        if any(not isinstance(item, MintQualification) for item in evidence):
            raise TypeError("mint alert gate requires MintQualification evidence")
        if len(evidence) > 1_000:
            raise ValueError("too many mint qualifications in one gate evaluation")
        if not items and not evidence:
            return ()
        with self._lock:
            now = self._now()
            for match in items:
                self._merge(match, now)
            touched = {item.catalyst_tweet_id for item in items}
            for qualification in evidence:
                touched.add(self._merge_qualification(qualification, now))
            for tweet_id in touched:
                self._decide(self._groups[tweet_id], now)
            self._prune(now)
            self._write()
            verdict_matches = {
                match.match_id: match
                for tweet_id in touched
                for match in self._groups[tweet_id].matches.values()
            }
            return tuple(self._verdict(item) for item in verdict_matches.values())

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            counts = Counter(group.outcome for group in self._groups.values())
            reasons = Counter(
                group.reason for group in self._groups.values() if group.reason
            )
            return {
                "schema": GATE_SCHEMA,
                "policy_started_at": self.policy_started_at.isoformat(),
                "groups": len(self._groups),
                "outcomes": dict(sorted(counts.items())),
                "reasons": dict(sorted(reasons.items())),
            }

    def audit_snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                **self.snapshot(),
                "candidate_groups": [
                    {
                        "tweet_id": group.tweet_id,
                        "outcome": group.outcome,
                        "reason": group.reason,
                        "selected_match_id": group.selected_match_id,
                        "qualification": (
                            None
                            if group.qualification is None
                            else qualification_payload(group.qualification)
                        ),
                        "updated_at": group.updated_at.isoformat(),
                        "matches": [
                            catalyst_mint_payload(item)
                            for item in group.matches.values()
                        ],
                    }
                    for group in self._groups.values()
                ],
            }

    def _merge(self, match: CatalystMintMatch, now: datetime) -> None:
        group = self._groups.get(match.catalyst_tweet_id)
        if group is None:
            group = _Group(
                match.catalyst_tweet_id, {}, "pending", "", None, None, now
            )
            self._groups[match.catalyst_tweet_id] = group
        old = group.matches.get(match.match_id)
        if old is not None and (
            old.exact_ca != match.exact_ca
            or old.catalyst_tweet_id != match.catalyst_tweet_id
            or old.token_created_at != match.token_created_at
        ):
            raise MintAlertGateError("mint alert match identity changed")
        group.matches[match.match_id] = match
        group.updated_at = now

    def _merge_qualification(
        self, qualification: MintQualification, now: datetime,
    ) -> str:
        groups = tuple(
            group for group in self._groups.values()
            if qualification.match_id in group.matches
        )
        if len(groups) != 1:
            raise MintAlertGateError(
                "mint qualification does not identify one retained match"
            )
        group = groups[0]
        if (
            group.qualification is not None
            and group.qualification != qualification
        ):
            raise MintAlertGateError("mint qualification evidence changed")
        group.qualification = qualification
        group.updated_at = now
        return group.tweet_id

    def _decide(self, group: _Group, now: datetime) -> None:
        exact_cas = {item.exact_ca for item in group.matches.values()}
        if group.outcome == MintAlertAction.ALERT.value and len(exact_cas) > 1:
            group.outcome = MintAlertAction.REJECT.value
            group.reason = "post_alert_multiple_exact_cas"
            group.updated_at = now
            return
        if group.outcome != "pending":
            return
        qualifications = (
            () if group.qualification is None else (group.qualification,)
        )
        decision = decide_mint_alert(
            tuple(group.matches.values()),
            now=now,
            qualifications=qualifications,
        )
        group.outcome = (
            "pending"
            if decision.action is MintAlertAction.WAIT
            else decision.action.value
        )
        group.reason = decision.reason
        group.selected_match_id = decision.selected_match_id
        group.updated_at = now

    def _verdict(self, match: CatalystMintMatch) -> MintAlertVerdict:
        group = self._groups[match.catalyst_tweet_id]
        if group.outcome == MintAlertAction.ALERT.value:
            if group.selected_match_id == match.match_id:
                if (
                    group.qualification is None
                    or group.qualification.action
                    is not MintQualificationAction.ALERT
                ):
                    raise MintAlertGateError(
                        "alert verdict lacks qualification approval"
                    )
                return MintAlertVerdict(
                    match,
                    MintAlertAction.ALERT,
                    group.reason,
                    group.qualification,
                )
            return MintAlertVerdict(
                match, MintAlertAction.REJECT, "canonical_mint_already_alerted"
            )
        action = (
            MintAlertAction.WAIT
            if group.outcome == "pending"
            else MintAlertAction(group.outcome)
        )
        qualification = (
            group.qualification
            if group.qualification is not None
            and group.qualification.match_id == match.match_id
            else None
        )
        return MintAlertVerdict(match, action, group.reason, qualification)

    def _prune(self, now: datetime) -> None:
        cutoff = now - self.retention
        retained = [
            item for item in self._groups.values()
            if item.updated_at >= cutoff
        ]
        retained.sort(key=lambda item: item.updated_at, reverse=True)
        if len(retained) > self.max_groups:
            raise RuntimeError("mint alert gate backlog exceeds its group limit")
        self._groups = {item.tweet_id: item for item in retained}

    def _write(self) -> None:
        write_mint_alert_gate_state(self.path, MintAlertGateState(
            policy_started_at=self.policy_started_at,
            groups=tuple(
                MintAlertGateGroup(
                    tweet_id=item.tweet_id,
                    matches=tuple(item.matches.values()),
                    outcome=item.outcome,
                    reason=item.reason,
                    selected_match_id=item.selected_match_id,
                    qualification=item.qualification,
                    updated_at=item.updated_at,
                )
                for item in self._groups.values()
            ),
        ))

    def _now(self) -> datetime:
        return utc_datetime(self.clock())


__all__ = ["GATE_SCHEMA", "MintAlertGate", "MintAlertGateError", "MintAlertVerdict"]
