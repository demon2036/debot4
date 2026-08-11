"""Leased Grok research worker for durable narrative jobs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..domain import DeBotSignal
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .job_payloads import (
    ACTIVE_TELEGRAM_POST,
    ACTIVE_X_POST,
    PASSIVE_DEBOT_SIGNAL,
    PASSIVE_MARKET_ANOMALY,
)
from .market_signal import MarketAnomaly
from .job_queue import NarrativeJobQueue
from .job_queue_models import JobStatus


class ResearchRuntime(Protocol):
    def research_active_post(self, post: XPost) -> object: ...

    def research_telegram_post(self, post: TelegramPost) -> object: ...

    def research_debot_signal(
        self, signal: DeBotSignal, *, anomaly: str | None = None
    ) -> object: ...

    def research_market_anomaly(self, anomaly: MarketAnomaly) -> object: ...


@dataclass(frozen=True, slots=True)
class WorkCycle:
    job_id: str | None
    status: JobStatus | None
    attempts: int = 0

    @property
    def idle(self) -> bool:
        return self.job_id is None


class NarrativeResearchWorker:
    """Lease one input, research it, then acknowledge or schedule a retry."""

    def __init__(
        self,
        queue: NarrativeJobQueue,
        runtime: ResearchRuntime,
        *,
        worker: str = "narrative-grok-1",
        lease_seconds: float = 120.0,
        retry_delay_seconds: float = 1.0,
    ) -> None:
        self.queue = queue
        self.runtime = runtime
        self.worker = worker
        self.lease_seconds = lease_seconds
        self.retry_delay_seconds = retry_delay_seconds

    def work_once(self) -> WorkCycle:
        job = self.queue.claim(self.worker, lease_seconds=self.lease_seconds)
        if job is None:
            return WorkCycle(None, None)
        try:
            self._research(job.kind, job.payload)
        except Exception as exc:
            failed = self.queue.fail(
                job.job_id,
                self.worker,
                job.lease_id,
                exc,
                retry=True,
                retry_delay_seconds=self.retry_delay_seconds,
            )
            return WorkCycle(failed.job_id, failed.status, failed.attempts)
        done = self.queue.ack(job.job_id, self.worker, job.lease_id)
        return WorkCycle(done.job_id, done.status, done.attempts)

    def _research(
        self,
        kind: str,
        payload: XPost | TelegramPost | DeBotSignal | MarketAnomaly,
    ) -> None:
        if kind == ACTIVE_X_POST and isinstance(payload, XPost):
            self.runtime.research_active_post(payload)
            return
        if kind == ACTIVE_TELEGRAM_POST and isinstance(payload, TelegramPost):
            self.runtime.research_telegram_post(payload)
            return
        if kind == PASSIVE_DEBOT_SIGNAL and isinstance(payload, DeBotSignal):
            self.runtime.research_debot_signal(payload)
            return
        if kind == PASSIVE_MARKET_ANOMALY and isinstance(payload, MarketAnomaly):
            self.runtime.research_market_anomaly(payload)
            return
        raise TypeError("narrative job kind and payload do not match")
