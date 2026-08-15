"""Coordinate one bounded Spark classification before mint-alert promotion."""

from __future__ import annotations

from collections.abc import Iterable
from concurrent.futures import Executor, Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from threading import RLock

from ..identity import utc_datetime, utc_now
from .catalyst_mint import CatalystMintMatch
from .mint_alert_gate import MintAlertGate, MintAlertVerdict
from .mint_alert_policy import MintAlertAction
from .mint_qualification import (
    MINT_QUALIFIER_MODEL,
    MintQualification,
    MintQualificationAction,
    MintQualifier,
)


@dataclass(frozen=True, slots=True)
class _Inflight:
    match: CatalystMintMatch
    started_at: datetime
    future: Future[MintQualification]


class MintAlertCoordinator:
    """Keep model latency off collectors while making approval mandatory."""

    def __init__(
        self,
        gate: MintAlertGate,
        qualifier: MintQualifier | None,
        *,
        clock=utc_now,
        executor: Executor | None = None,
    ) -> None:
        if qualifier is None and executor is not None:
            raise ValueError("a mint qualifier is required with an executor")
        self.gate = gate
        self.qualifier = qualifier
        self.clock = clock
        self._executor = (
            None
            if qualifier is None
            else executor or ThreadPoolExecutor(
                max_workers=1, thread_name_prefix="mint-spark"
            )
        )
        self._lock = RLock()
        self._waiting: dict[str, CatalystMintMatch] = {}
        self._qualified: set[str] = set()
        self._inflight: _Inflight | None = None
        self._closed = False
        self.submitted = 0
        self.completed = 0
        self.failed = 0

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            executor = self._executor
        if executor is not None:
            executor.shutdown(wait=True, cancel_futures=True)

    def evaluate(
        self, matches: Iterable[CatalystMintMatch],
    ) -> tuple[MintAlertVerdict, ...]:
        items = tuple(matches)
        with self._lock:
            if self._closed:
                raise RuntimeError("mint alert coordinator is closed")
            completed = self._harvest()
            verdicts = self.gate.evaluate(items, completed)
            output = {item.match.match_id: item for item in verdicts}
            self._track(verdicts)
            self._schedule()
            completed = self._harvest()
            if completed:
                followup = self.gate.evaluate((), completed)
                output.update((item.match.match_id, item) for item in followup)
                self._track(followup)
                self._schedule()
            return tuple(output.values())

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                **self.gate.snapshot(),
                "qualifier_configured": self.qualifier is not None,
                "qualifier_model": (
                    None
                    if self.qualifier is None
                    else MINT_QUALIFIER_MODEL
                ),
                "qualification_inflight": self._inflight is not None,
                "qualification_waiting": len(self._waiting),
                "qualification_submitted": self.submitted,
                "qualification_completed": self.completed,
                "qualification_failed": self.failed,
            }

    def audit_snapshot(self) -> dict[str, object]:
        with self._lock:
            return {**self.gate.audit_snapshot(), **self.snapshot()}

    def _track(self, verdicts: tuple[MintAlertVerdict, ...]) -> None:
        for verdict in verdicts:
            match_id = verdict.match.match_id
            if verdict.action is MintAlertAction.WAIT:
                self._waiting[match_id] = verdict.match
                if verdict.qualification is not None:
                    self._qualified.add(match_id)
            else:
                self._waiting.pop(match_id, None)
                self._qualified.discard(match_id)

    def _schedule(self) -> None:
        if self.qualifier is None or self._executor is None:
            return
        if self._inflight is not None:
            return
        candidates = tuple(
            item for match_id, item in self._waiting.items()
            if match_id not in self._qualified
        )
        if not candidates:
            return
        match = min(
            candidates,
            key=lambda item: (item.catalyst_created_at, item.match_id),
        )
        started = utc_datetime(self.clock())
        future = self._executor.submit(self.qualifier.qualify, match)
        self._inflight = _Inflight(match, started, future)
        self.submitted += 1

    def _harvest(self) -> tuple[MintQualification, ...]:
        inflight = self._inflight
        if inflight is None or not inflight.future.done():
            return ()
        self._inflight = None
        try:
            result = inflight.future.result()
            if result.match_id != inflight.match.match_id:
                raise ValueError("mint qualifier returned the wrong match")
        except Exception as exc:
            failed_at = max(utc_datetime(self.clock()), inflight.started_at)
            result = MintQualification(
                inflight.match.match_id,
                MintQualificationAction.REJECT,
                inflight.started_at,
                failed_at,
                MINT_QUALIFIER_MODEL,
                f"spark_error_{type(exc).__name__}"[:128],
            )
            self.failed += 1
        else:
            self.completed += 1
        self._qualified.add(result.match_id)
        return (result,)


__all__ = ["MintAlertCoordinator"]
