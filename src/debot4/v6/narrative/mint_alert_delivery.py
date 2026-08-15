"""Independent retry loop and presentation adapter for mint alerts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import json
import math
import sys
from time import monotonic
from typing import Protocol, TextIO

from ..identity import utc_datetime, utc_now
from .mint_alert import MintAlert
from .mint_alert_store import MintAlertStore


DEFAULT_ALERT_POLL_SECONDS = 0.25
DEFAULT_ALERT_RETRY_SECONDS = 2.0


class MintAlertSink(Protocol):
    def send(self, alert: MintAlert, *, delivered_at: datetime) -> None: ...


class JsonLineMintAlertSink:
    """Emit one immediately flushable, credential-free JSON record per CA."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = sys.stderr if stream is None else stream

    def send(self, alert: MintAlert, *, delivered_at: datetime) -> None:
        payload = alert.as_public_dict(delivered_at=delivered_at)
        self.stream.write(json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ) + "\n")
        self.stream.flush()


@dataclass(frozen=True, slots=True)
class MintAlertDispatchCycle:
    attempted: int = 0
    delivered: int = 0
    failed: int = 0


class MintAlertDispatcher:
    """Deliver the durable outbox without sharing the research worker path."""

    def __init__(
        self,
        store: MintAlertStore,
        sink: MintAlertSink,
        *,
        poll_seconds: float = DEFAULT_ALERT_POLL_SECONDS,
        retry_seconds: float = DEFAULT_ALERT_RETRY_SECONDS,
        batch_size: int = 50,
        timer: Callable[[], float] = monotonic,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        if not math.isfinite(poll_seconds) or not 0.05 <= poll_seconds <= 2:
            raise ValueError("mint alert poll must be between 0.05 and 2 seconds")
        if not math.isfinite(retry_seconds) or not 0.25 <= retry_seconds <= 60:
            raise ValueError("mint alert retry must be between 0.25 and 60 seconds")
        if isinstance(batch_size, bool) or not 1 <= batch_size <= 500:
            raise ValueError("mint alert batch size must be between 1 and 500")
        self.store = store
        self.sink = sink
        self.poll_seconds = float(poll_seconds)
        self.retry_seconds = float(retry_seconds)
        self.batch_size = batch_size
        self.timer = timer
        self.clock = clock
        self._next_poll_at = 0.0
        self.attempted = 0
        self.delivered = 0
        self.failed = 0
        self.last_error_type: str | None = None
        self.last_delivered_at: datetime | None = None

    def dispatch_once(self) -> MintAlertDispatchCycle:
        tick = float(self.timer())
        if not math.isfinite(tick):
            raise ValueError("mint alert timer must be finite")
        if tick < self._next_poll_at:
            return MintAlertDispatchCycle()
        self._next_poll_at = tick + self.poll_seconds
        now = utc_datetime(self.clock())
        alerts = self.store.pending(now=now, limit=self.batch_size)
        delivered = failed = 0
        for alert in alerts:
            attempted_at = utc_datetime(self.clock())
            self.attempted += 1
            try:
                self.sink.send(alert, delivered_at=attempted_at)
            except Exception as exc:
                error_type = type(exc).__name__
                self.store.mark_failed(
                    alert.alert_id,
                    attempted_at=attempted_at,
                    retry_seconds=self.retry_seconds,
                    error_type=error_type,
                )
                self.failed += 1
                failed += 1
                self.last_error_type = error_type
                continue
            self.store.mark_delivered(alert.alert_id, attempted_at)
            self.delivered += 1
            delivered += 1
            self.last_error_type = None
            self.last_delivered_at = attempted_at
        return MintAlertDispatchCycle(len(alerts), delivered, failed)

    def snapshot(self) -> dict[str, object]:
        return {
            "poll_seconds": self.poll_seconds,
            "retry_seconds": self.retry_seconds,
            "attempted": self.attempted,
            "delivered": self.delivered,
            "failed": self.failed,
            "last_error_type": self.last_error_type,
            "last_delivered_at": (
                None
                if self.last_delivered_at is None
                else self.last_delivered_at.isoformat()
            ),
            "model_on_critical_path": True,
        }
