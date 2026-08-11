"""Restart-safe DeBot signals that trigger narrative investigation only."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
from time import monotonic

from ..debot import DeBotClient
from ..debot.http import DeBotHttp
from ..domain import DeBotSignal


CHECKPOINT_SCHEMA = "debot4.v6.narrative_debot_feed.v1"
DEFAULT_POLL_SECONDS = 2.0
_ROOT_FIELDS = frozenset({"schema", "seen_signal_ids"})


class DeBotFeedCheckpointError(ValueError):
    """The feed checkpoint is missing required structure or safe values."""


@dataclass(frozen=True, slots=True)
class NarrativeDeBotCandidate:
    """A research candidate; this record never authorizes a trade."""

    signal: DeBotSignal
    reasons: tuple[str, ...]
    anomaly: str | None = None

    @property
    def authorizes_trade(self) -> bool:
        return False


class JsonDeBotFeedCheckpoint:
    """Minimal exact signal-ID set persisted with an atomic private write."""

    def __init__(
        self, path: str | Path, *, max_signal_ids: int = 100_000,
    ) -> None:
        if not 1 <= max_signal_ids <= 1_000_000:
            raise ValueError("max_signal_ids must be between 1 and 1000000")
        self.path = Path(path)
        self.max_signal_ids = max_signal_ids
        self._secure_parent()
        self.initialized = self.path.exists()
        self._seen = self._read() if self.initialized else set()

    def has_seen(self, signal_id: str) -> bool:
        return signal_id in self._seen

    def commit(self, signal_ids: set[str]) -> None:
        merged = self._seen | signal_ids
        if len(merged) > self.max_signal_ids:
            raise DeBotFeedCheckpointError("DeBot feed checkpoint ID limit exceeded")
        self._write(merged)
        self._seen = merged
        self.initialized = True

    def snapshot(self) -> frozenset[str]:
        return frozenset(self._seen)

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists():
            if not self.path.is_file():
                raise DeBotFeedCheckpointError("checkpoint is not a regular file")
            self.path.chmod(0o600)

    def _read(self) -> set[str]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DeBotFeedCheckpointError("invalid DeBot feed checkpoint JSON") from exc
        except OSError as exc:
            raise DeBotFeedCheckpointError("cannot read DeBot feed checkpoint") from exc
        if not isinstance(raw, dict) or set(raw) != _ROOT_FIELDS:
            raise DeBotFeedCheckpointError("invalid DeBot feed checkpoint schema")
        if raw.get("schema") != CHECKPOINT_SCHEMA:
            raise DeBotFeedCheckpointError("unsupported DeBot feed checkpoint schema")
        items = raw.get("seen_signal_ids")
        if not isinstance(items, list) or len(items) > self.max_signal_ids:
            raise DeBotFeedCheckpointError("invalid DeBot feed signal IDs")
        if any(not _valid_signal_id(item) for item in items):
            raise DeBotFeedCheckpointError("invalid DeBot feed signal ID")
        result = set(items)
        if len(result) != len(items):
            raise DeBotFeedCheckpointError("duplicate DeBot feed signal ID")
        return result

    def _write(self, signal_ids: set[str]) -> None:
        self._secure_parent()
        document = json.dumps(
            {
                "schema": CHECKPOINT_SCHEMA,
                "seen_signal_ids": sorted(signal_ids),
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                temporary.chmod(0o600)
                stream.write(document + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


class NarrativeDeBotFeed:
    """Fetch one official DeBot page for an upper-layer high-frequency loop."""

    def __init__(
        self,
        client: DeBotClient,
        checkpoint_path: str | Path,
        *,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        max_signal_ids: int = 100_000,
        timer: Callable[[], float] = monotonic,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        self.client = client
        self.poll_seconds = float(poll_seconds)
        self._timer = timer
        self._next_poll_at = 0.0
        self.checkpoint = JsonDeBotFeedCheckpoint(
            checkpoint_path, max_signal_ids=max_signal_ids,
        )

    @classmethod
    def from_credentials(
        cls,
        checkpoint_path: str | Path,
        *,
        credential_file: str | Path,
        timeout_seconds: float = 5.0,
        max_response_bytes: int = 2_000_000,
        poll_seconds: float = DEFAULT_POLL_SECONDS,
        max_signal_ids: int = 100_000,
    ) -> "NarrativeDeBotFeed":
        transport = DeBotHttp(
            credential_file=credential_file,
            timeout_seconds=timeout_seconds,
            max_response_bytes=max_response_bytes,
        )
        return cls(
            DeBotClient(transport), checkpoint_path,
            poll_seconds=poll_seconds, max_signal_ids=max_signal_ids,
        )

    def close(self) -> None:
        self.client.close()

    def poll_once(
        self,
        *,
        anomaly: str | None = None,
        accept: Callable[[tuple[NarrativeDeBotCandidate, ...]], object] | None = None,
    ) -> tuple[NarrativeDeBotCandidate, ...]:
        """Advance only after the downstream durable acceptor succeeds."""
        now = self._timer()
        if now < self._next_poll_at:
            return ()
        self._next_poll_at = now + self.poll_seconds
        page = self.client.fetch_page()
        ordered = sorted(
            page.signals,
            key=lambda item: (item.event_at, item.available_at, item.signal_id),
        )
        page_ids: set[str] = set()
        unseen: list[DeBotSignal] = []
        for signal in ordered:
            if not _valid_signal_id(signal.signal_id):
                raise ValueError("DeBot page contains an invalid signal ID")
            if signal.signal_id in page_ids:
                continue
            page_ids.add(signal.signal_id)
            if not self.checkpoint.has_seen(signal.signal_id):
                unseen.append(signal)

        candidates = tuple(
            candidate
            for signal in unseen
            if (candidate := select_narrative_candidate(signal, anomaly=anomaly))
            is not None
        )
        if accept is not None:
            accept(candidates)
        self.checkpoint.commit(page_ids)
        return candidates


def select_narrative_candidate(
    signal: DeBotSignal, *, anomaly: str | None = None,
) -> NarrativeDeBotCandidate | None:
    """Explain why a DeBot item deserves research without making a buy call."""
    normalized_anomaly = _normalize_anomaly(anomaly)
    kind = signal.signal_kind.strip().casefold().replace("-", "_")
    group = signal.group_name.split("#", 1)[0].strip().casefold()
    reasons: list[str] = []
    if signal.kol_buy_qualified:
        reasons.append("qualified_kol")
    if kind == "kol" or group == "kol":
        reasons.append("kol_signal_or_group")
    if kind in {"smart_money", "smartmoney"} or group == "smartmoney":
        reasons.append("smart_money_signal_or_group")
    if normalized_anomaly is not None:
        reasons.append("explicit_anomaly")
    if not reasons:
        return None
    return NarrativeDeBotCandidate(signal, tuple(reasons), normalized_anomaly)


def _normalize_anomaly(value: str | None) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise TypeError("anomaly must be a string or None")
    text = value.strip()
    if len(text) > 2_000:
        raise ValueError("anomaly exceeds 2000 characters")
    return text or None


def _valid_signal_id(value: object) -> bool:
    return isinstance(value, str) and 0 < len(value) <= 128 and value == value.strip()
