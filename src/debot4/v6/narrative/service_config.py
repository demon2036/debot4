"""Validated concurrency and retry timings for the narrative service."""

from __future__ import annotations

from dataclasses import dataclass
import math


MIN_COLLECTOR_SECONDS = 0.05
MAX_COLLECTOR_SECONDS = 2.0


@dataclass(frozen=True, slots=True)
class NarrativeServiceConfig:
    """Bounded timings: scheduling is fast and never uses a 30-second tick."""

    collector_seconds: float = 0.25
    worker_idle_seconds: float = 0.25
    lease_seconds: float = 120.0
    retry_delay_seconds: float = 1.0
    max_attempts: int = 3
    research_workers: int = 1

    def __post_init__(self) -> None:
        _seconds(
            "collector_seconds",
            self.collector_seconds,
            MIN_COLLECTOR_SECONDS,
            MAX_COLLECTOR_SECONDS,
        )
        _seconds("worker_idle_seconds", self.worker_idle_seconds, 0.01, 2.0)
        _seconds("lease_seconds", self.lease_seconds, 0.01, 86_400.0)
        _seconds("retry_delay_seconds", self.retry_delay_seconds, 0.0, 86_400.0)
        if isinstance(self.max_attempts, bool) or not 1 <= self.max_attempts <= 100:
            raise ValueError("max_attempts must be between 1 and 100")
        if (
            isinstance(self.research_workers, bool)
            or not 1 <= self.research_workers <= 16
        ):
            raise ValueError("research_workers must be between 1 and 16")


def _seconds(name: str, value: float, minimum: float, maximum: float) -> None:
    if isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be a finite number")
    if not minimum <= float(value) <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}")
