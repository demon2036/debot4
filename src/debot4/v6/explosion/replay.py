"""Validated historical replays for causal regression, never trading claims."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Mapping


_EVM_CA = re.compile(r"0x[a-f0-9]{40}")
_WAVE_KINDS = frozenset({"initial_launch", "secondary_catalyst"})
_SIGNAL_ROLES = frozenset({"catalyst", "market", "confirmation", "candidate"})
_CANDIDATE_STATUSES = frozenset({"active_verified", "research_candidate", "disabled_no_evidence"})


@dataclass(frozen=True, slots=True)
class ReplayMoment:
    label: str
    occurred_at: datetime
    role: str
    source_url: str
    evidence: str
    offset_from_move_seconds: float | None = None

    def __post_init__(self) -> None:
        occurred = _time(self.occurred_at)
        role = self.role.strip().casefold()
        if not self.label.strip() or role not in _SIGNAL_ROLES:
            raise ValueError("replay moment identity is invalid")
        if not self.source_url.startswith("https://") or not self.evidence.strip():
            raise ValueError("replay moment evidence is incomplete")
        object.__setattr__(self, "occurred_at", occurred)
        object.__setattr__(self, "role", role)


@dataclass(frozen=True, slots=True)
class MarketWave:
    wave_id: str
    kind: str
    move_started_at: datetime
    entry_fdv_usd: float
    peak_fdv_usd: float
    peak_at: datetime
    precision: str
    moments: tuple[ReplayMoment, ...]

    def __post_init__(self) -> None:
        started, peak = _time(self.move_started_at), _time(self.peak_at)
        kind = self.kind.strip().casefold()
        if not self.wave_id.strip() or kind not in _WAVE_KINDS or peak < started:
            raise ValueError("market wave identity or timing is invalid")
        if self.entry_fdv_usd <= 0 or self.peak_fdv_usd < self.entry_fdv_usd:
            raise ValueError("market wave valuation is invalid")
        if not self.precision.strip() or not self.moments:
            raise ValueError("market wave requires precision and evidence moments")
        object.__setattr__(self, "move_started_at", started)
        object.__setattr__(self, "peak_at", peak)
        object.__setattr__(self, "kind", kind)

    @property
    def peak_multiple(self) -> float:
        return self.peak_fdv_usd / self.entry_fdv_usd


@dataclass(frozen=True, slots=True)
class ResearchCandidate:
    subject: str
    kind: str
    status: str
    evidence_urls: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        status = self.status.strip().casefold()
        if status not in _CANDIDATE_STATUSES or not self.subject.strip() or not self.kind.strip():
            raise ValueError("research candidate is invalid")
        if not self.reason.strip() or not self.evidence_urls:
            raise ValueError("research candidate requires a reason and evidence")
        if any(not item.startswith("https://") for item in self.evidence_urls):
            raise ValueError("research candidate evidence must use HTTPS")
        object.__setattr__(self, "status", status)


@dataclass(frozen=True, slots=True)
class ExplosionReplay:
    case_id: str
    token_name: str
    chain: str
    token_address: str
    waves: tuple[MarketWave, ...]
    candidates: tuple[ResearchCandidate, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        address = self.token_address.strip().casefold()
        ids = [item.wave_id for item in self.waves]
        if not self.case_id.strip() or not self.token_name.strip() or not _EVM_CA.fullmatch(address):
            raise ValueError("explosion replay identity is invalid")
        if len(self.waves) < 2 or len(ids) != len(set(ids)):
            raise ValueError("explosion replay requires at least two unique waves")
        if not self.limitations:
            raise ValueError("explosion replay must preserve limitations")
        object.__setattr__(self, "chain", self.chain.strip().casefold())
        object.__setattr__(self, "token_address", address)


def load_replay(path: str | Path) -> ExplosionReplay:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, Mapping) or raw.get("schema") != "debot4.explosion_replay.v1":
        raise ValueError("unsupported explosion replay schema")
    return ExplosionReplay(
        case_id=str(raw.get("case_id") or ""),
        token_name=str(raw.get("token_name") or ""),
        chain=str(raw.get("chain") or ""),
        token_address=str(raw.get("token_address") or ""),
        waves=tuple(_wave(item) for item in _rows(raw, "waves")),
        candidates=tuple(_candidate(item) for item in _rows(raw, "candidates")),
        limitations=tuple(str(item) for item in _rows(raw, "limitations")),
    )


def _wave(value: object) -> MarketWave:
    row = _mapping(value)
    return MarketWave(
        wave_id=str(row.get("wave_id") or ""), kind=str(row.get("kind") or ""),
        move_started_at=_parse_time(row.get("move_started_at")),
        entry_fdv_usd=float(row.get("entry_fdv_usd") or 0),
        peak_fdv_usd=float(row.get("peak_fdv_usd") or 0),
        peak_at=_parse_time(row.get("peak_at")), precision=str(row.get("precision") or ""),
        moments=tuple(_moment(item) for item in _rows(row, "moments")),
    )


def _moment(value: object) -> ReplayMoment:
    row = _mapping(value)
    offset = row.get("offset_from_move_seconds")
    return ReplayMoment(
        str(row.get("label") or ""), _parse_time(row.get("occurred_at")),
        str(row.get("role") or ""), str(row.get("source_url") or ""),
        str(row.get("evidence") or ""), None if offset is None else float(offset),
    )


def _candidate(value: object) -> ResearchCandidate:
    row = _mapping(value)
    return ResearchCandidate(
        str(row.get("subject") or ""), str(row.get("kind") or ""),
        str(row.get("status") or ""),
        tuple(str(item) for item in _rows(row, "evidence_urls")),
        str(row.get("reason") or ""),
    )


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("explosion replay row must be an object")
    return value


def _rows(value: Mapping[str, object], key: str) -> list[object]:
    rows = value.get(key)
    if not isinstance(rows, list):
        raise ValueError(f"explosion replay {key} must be a list")
    return rows


def _parse_time(value: object) -> datetime:
    return _time(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _time(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("replay timestamps must be timezone-aware")
    return value.astimezone(timezone.utc)
