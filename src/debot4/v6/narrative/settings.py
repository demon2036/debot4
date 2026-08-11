"""Small environment-owned settings for the narrative-only runtime."""

from __future__ import annotations

from dataclasses import dataclass
import math
import os
from pathlib import Path
from typing import Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True, slots=True)
class NarrativeSettings:
    """Validated paths and cadences; credentials remain outside this object."""

    state_dir: Path
    debot_cookie_file: Path
    telegram_realtime_config: Path | None = None
    collector_tick_seconds: float = 0.25
    debot_poll_seconds: float = 2.0
    market_poll_seconds: float = 5.0
    worker_idle_seconds: float = 0.25
    retry_delay_seconds: float = 5.0
    lease_seconds: float = 240.0
    x_timeout_seconds: float = 8.0
    telegram_timeout_seconds: float = 8.0
    telegram_realtime_retry_seconds: float = 2.0
    debot_timeout_seconds: float = 5.0
    market_timeout_seconds: float = 5.0
    max_response_bytes: int = 2_000_000

    def __post_init__(self) -> None:
        state = Path(self.state_dir).expanduser().resolve()
        debot_cookie = Path(self.debot_cookie_file).expanduser().resolve()
        realtime = (
            None
            if self.telegram_realtime_config is None
            else Path(self.telegram_realtime_config).expanduser().resolve()
        )
        cadences = (
            self.collector_tick_seconds,
            self.debot_poll_seconds,
            self.market_poll_seconds,
            self.worker_idle_seconds,
            self.retry_delay_seconds,
            self.lease_seconds,
            self.x_timeout_seconds,
            self.telegram_timeout_seconds,
            self.telegram_realtime_retry_seconds,
            self.debot_timeout_seconds,
            self.market_timeout_seconds,
        )
        if any(not math.isfinite(value) or value <= 0 for value in cadences):
            raise ValueError("narrative runtime intervals must be positive and finite")
        if not 0.05 <= self.collector_tick_seconds <= 2:
            raise ValueError("collector tick must be between 0.05 and 2 seconds")
        if not 0.25 <= self.debot_poll_seconds <= 5:
            raise ValueError("DeBot poll must be between 0.25 and 5 seconds")
        if not 0.5 <= self.market_poll_seconds <= 15:
            raise ValueError("market poll must be between 0.5 and 15 seconds")
        if not 0.05 <= self.worker_idle_seconds <= 5:
            raise ValueError("worker idle must be between 0.05 and 5 seconds")
        if not 30 <= self.lease_seconds <= 3_600:
            raise ValueError("worker lease must be between 30 and 3600 seconds")
        if not 1_024 <= self.max_response_bytes <= 8 * 1_024 * 1_024:
            raise ValueError("response byte limit must be between 1 KiB and 8 MiB")
        object.__setattr__(self, "state_dir", state)
        object.__setattr__(self, "debot_cookie_file", debot_cookie)
        object.__setattr__(self, "telegram_realtime_config", realtime)

    @classmethod
    def from_env(
        cls, environ: Mapping[str, str] | None = None
    ) -> "NarrativeSettings":
        env = os.environ if environ is None else environ
        return cls(
            state_dir=Path(env.get(
                "DEBOT4_NARRATIVE_STATE_DIR", PROJECT_ROOT / "var" / "narrative"
            )),
            debot_cookie_file=Path(env.get(
                "DEBOT4_DEBOT_COOKIE_FILE",
                Path.home() / ".config" / "debot4" / "credentials"
                / "debot_cookies.json",
            )),
            telegram_realtime_config=_optional_path(
                env.get("DEBOT4_TELEGRAM_REALTIME_CONFIG", "")
            ),
            collector_tick_seconds=_number(env, "DEBOT4_COLLECTOR_TICK_SECONDS", 0.25),
            debot_poll_seconds=_number(env, "DEBOT4_DEBOT_POLL_SECONDS", 2.0),
            market_poll_seconds=_number(env, "DEBOT4_MARKET_POLL_SECONDS", 5.0),
            worker_idle_seconds=_number(env, "DEBOT4_WORKER_IDLE_SECONDS", 0.25),
            retry_delay_seconds=_number(env, "DEBOT4_RETRY_DELAY_SECONDS", 5.0),
            lease_seconds=_number(env, "DEBOT4_JOB_LEASE_SECONDS", 240.0),
            x_timeout_seconds=_number(env, "DEBOT4_X_TIMEOUT_SECONDS", 8.0),
            telegram_timeout_seconds=_number(
                env, "DEBOT4_TELEGRAM_TIMEOUT_SECONDS", 8.0
            ),
            telegram_realtime_retry_seconds=_number(
                env, "DEBOT4_TELEGRAM_REALTIME_RETRY_SECONDS", 2.0
            ),
            debot_timeout_seconds=_number(env, "DEBOT4_DEBOT_TIMEOUT_SECONDS", 5.0),
            market_timeout_seconds=_number(
                env, "DEBOT4_MARKET_TIMEOUT_SECONDS", 5.0
            ),
            max_response_bytes=_integer(
                env, "DEBOT4_MAX_RESPONSE_BYTES", 2_000_000
            ),
        )

    @property
    def x_checkpoint_path(self) -> Path:
        return self.state_dir / "x-checkpoints.json"

    @property
    def debot_checkpoint_path(self) -> Path:
        return self.state_dir / "debot-checkpoints.json"

    @property
    def telegram_checkpoint_path(self) -> Path:
        return self.state_dir / "telegram-checkpoints.json"

    @property
    def market_checkpoint_path(self) -> Path:
        return self.state_dir / "market-anomalies.json"

    @property
    def queue_database(self) -> Path:
        return self.state_dir / "jobs.sqlite3"

    @property
    def research_database(self) -> Path:
        return self.state_dir / "research.sqlite3"


def _number(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, str(default)))
    except ValueError:
        raise ValueError(f"{key} must be numeric") from None


def _integer(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key, str(default))
    try:
        if any(char in value for char in ".eE"):
            raise ValueError
        return int(value)
    except ValueError:
        raise ValueError(f"{key} must be an integer") from None


def _optional_path(value: str) -> Path | None:
    return Path(value.strip()) if value.strip() else None
