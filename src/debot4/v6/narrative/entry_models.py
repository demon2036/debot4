"""Independent decision-time quote, head, and entry authorization types."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import math

from .models import aware_utc


EXECUTION_SCHEMA = "v6.execution_boundary.v1"
ENTRY_SCHEMA = "v6.entry_authorization.v1"


class ExecutionStatus(str, Enum):
    PASS = "PASS"
    REQUOTE = "REQUOTE"
    REJECT = "REJECT"


class EntryStatus(str, Enum):
    COMMIT = "COMMIT"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class QuoteBoundary:
    """Atomic route-and-FDV quote produced at one exact execution block."""

    token_address: str
    block_number: int
    block_hash: str
    block_timestamp: datetime
    completed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "token_address", self.token_address.strip().lower())
        object.__setattr__(self, "block_hash", self.block_hash.strip().lower())
        object.__setattr__(
            self, "block_timestamp", aware_utc(self.block_timestamp, "block_timestamp")
        )
        object.__setattr__(
            self, "completed_at", aware_utc(self.completed_at, "completed_at")
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "token_address": self.token_address,
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "block_timestamp": self.block_timestamp.isoformat(),
            "completed_at": self.completed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class HeadBoundary:
    block_number: int
    block_hash: str
    observed_at: datetime

    def __post_init__(self) -> None:
        object.__setattr__(self, "block_hash", self.block_hash.strip().lower())
        object.__setattr__(
            self, "observed_at", aware_utc(self.observed_at, "observed_at")
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "block_number": self.block_number,
            "block_hash": self.block_hash,
            "observed_at": self.observed_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ExecutionPolicy:
    max_quote_age_seconds: float
    max_head_age_seconds: float
    max_head_lag_blocks: int
    max_future_skew_seconds: float = 0.05

    def __post_init__(self) -> None:
        for name in (
            "max_quote_age_seconds",
            "max_head_age_seconds",
            "max_future_skew_seconds",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and non-negative")
            object.__setattr__(self, name, value)
        lag = self.max_head_lag_blocks
        if not isinstance(lag, int) or isinstance(lag, bool) or lag < 0:
            raise ValueError("max_head_lag_blocks must be a non-negative integer")

    def to_payload(self) -> dict[str, object]:
        return {
            "max_quote_age_seconds": self.max_quote_age_seconds,
            "max_head_age_seconds": self.max_head_age_seconds,
            "max_head_lag_blocks": self.max_head_lag_blocks,
            "max_future_skew_seconds": self.max_future_skew_seconds,
        }


@dataclass(frozen=True, slots=True)
class ExecutionDecision:
    status: ExecutionStatus
    reasons: tuple[str, ...]
    checked_at: datetime
    identity: str
    identity_hash: str
    quote_age_seconds: float | None = None
    head_age_seconds: float | None = None
    head_lag_blocks: int | None = None

    @property
    def can_commit(self) -> bool:
        return self.status is ExecutionStatus.PASS

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": EXECUTION_SCHEMA,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "checked_at": self.checked_at.isoformat(),
            "identity": self.identity,
            "identity_hash": self.identity_hash,
            "quote_age_seconds": self.quote_age_seconds,
            "head_age_seconds": self.head_age_seconds,
            "head_lag_blocks": self.head_lag_blocks,
        }


@dataclass(frozen=True, slots=True)
class EntryAuthorization:
    status: EntryStatus
    reasons: tuple[str, ...]
    identity: str
    identity_hash: str

    @property
    def can_commit(self) -> bool:
        return self.status is EntryStatus.COMMIT
