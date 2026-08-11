"""Immutable, audit-friendly historical narrative case records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from urllib.parse import urlsplit


_EVM_CA = re.compile(r"0x[a-fA-F0-9]{40}")
_EVIDENCE_KINDS = frozenset({"x", "telegram", "wallet", "chain", "report"})
_ROLES = frozenset({
    "origin", "project", "early_binding", "wallet_lead", "amplifier",
    "scanner", "posthoc", "counter_signal", "unknown",
})
_PHASES = frozenset({"before", "launch", "during", "after", "unknown"})
_CONFIDENCE = frozenset({"verified", "corroborated", "reported", "unknown"})


@dataclass(frozen=True, slots=True)
class CaseEvidence:
    source_kind: str
    source_name: str
    role: str
    phase: str
    confidence: str
    note: str
    source_url: str = ""
    actor_handle: str = ""
    observed_at: str = ""
    exact_ca: bool = False
    monitor: bool = False

    def __post_init__(self) -> None:
        if self.source_kind not in _EVIDENCE_KINDS:
            raise ValueError("unsupported evidence source kind")
        if self.role not in _ROLES or self.phase not in _PHASES:
            raise ValueError("unsupported evidence role or phase")
        if self.confidence not in _CONFIDENCE:
            raise ValueError("unsupported evidence confidence")
        if not self.source_name.strip() or not self.note.strip():
            raise ValueError("evidence source and note are required")
        if self.source_url and not _https_url(self.source_url):
            raise ValueError("evidence URL must use HTTPS")
        if self.observed_at:
            _aware_datetime(self.observed_at)
        if self.monitor and not self.actor_handle.strip():
            raise ValueError("monitored X evidence requires an actor handle")

    def as_public_dict(self) -> dict[str, object]:
        return {
            "source_kind": self.source_kind,
            "source_name": self.source_name,
            "role": self.role,
            "phase": self.phase,
            "confidence": self.confidence,
            "note": self.note,
            "source_url": self.source_url,
            "actor_handle": self.actor_handle,
            "observed_at": self.observed_at,
            "exact_ca": self.exact_ca,
            "monitor": self.monitor,
        }


@dataclass(frozen=True, slots=True)
class HistoricalCase:
    case_id: str
    chain: str
    token: str
    asset_ref: str
    first_seen_at: str
    coverage: str
    metric_note: str
    peak_proxy_usd: float | None = None
    multiple_proxy: float | None = None
    max_drawdown_pct: float | None = None
    evidence: tuple[CaseEvidence, ...] = ()
    risk_notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not all((self.case_id.strip(), self.chain.strip(), self.token.strip())):
            raise ValueError("case identity is required")
        if self.asset_ref and self.asset_ref.startswith("0x"):
            if not _EVM_CA.fullmatch(self.asset_ref):
                raise ValueError("invalid EVM contract address")
        if self.first_seen_at:
            _aware_datetime(self.first_seen_at)
        for value in (self.peak_proxy_usd, self.multiple_proxy):
            if value is not None and value < 0:
                raise ValueError("case metrics cannot be negative")
        if self.max_drawdown_pct is not None and not 0 <= self.max_drawdown_pct <= 100:
            raise ValueError("drawdown must be between zero and one hundred")

    def as_public_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "chain": self.chain,
            "token": self.token,
            "asset_ref": self.asset_ref,
            "first_seen_at": self.first_seen_at,
            "coverage": self.coverage,
            "metric_note": self.metric_note,
            "peak_proxy_usd": self.peak_proxy_usd,
            "multiple_proxy": self.multiple_proxy,
            "max_drawdown_pct": self.max_drawdown_pct,
            "evidence": [item.as_public_dict() for item in self.evidence],
            "risk_notes": list(self.risk_notes),
        }


def evidence(
    source_kind: str, source_name: str, role: str, phase: str,
    confidence: str, note: str, *, url: str = "", actor: str = "",
    at: str = "", exact_ca: bool = False, monitor: bool = False,
) -> CaseEvidence:
    return CaseEvidence(
        source_kind, source_name, role, phase, confidence, note,
        url, actor, at, exact_ca, monitor,
    )


def case(
    case_id: str, chain: str, token: str, asset_ref: str, first_seen_at: str,
    coverage: str, metric_note: str, *, peak: float | None = None,
    multiple: float | None = None, drawdown: float | None = None,
    evidence_items: tuple[CaseEvidence, ...] = (), risks: tuple[str, ...] = (),
) -> HistoricalCase:
    return HistoricalCase(
        case_id, chain, token, asset_ref, first_seen_at, coverage, metric_note,
        peak, multiple, drawdown, evidence_items, risks,
    )


def _aware_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("case timestamps must be timezone-aware")
    return parsed


def _https_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme == "https" and bool(parsed.hostname)
