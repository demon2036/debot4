"""Historical KOL evidence and causally valid entry decisions."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from . import rows
from .codec import (
    KOL_SOURCES,
    OFFICIAL_KOL_SOURCE,
    RANKS_KOL_SOURCE,
    canonical_json,
    chain as clean_chain,
    text,
    to_us,
    token,
)
from .models import EntryDecision, HistoricalKolEvidence, InsertResult


_EVIDENCE_COLUMNS = (
    "evidence_id", "chain", "token_address", "signal_id", "event_at_us",
    "available_at_us", "qualified_at_us", "source", "evidence_uri",
    "metadata_json",
)
_DECISION_COLUMNS = (
    "decision_id", "candidate_id", "signal_id", "kol_evidence_id",
    "decided_at_us", "status", "reason", "source", "strategy_version",
    "metadata_json",
)

_RANKS_ANNOTATIONS: dict[str, object] = {
    "claim_type": "kol_count_increase",
    "evidence_quality": "provider_aggregate_asserted",
    "evidence_semantics": "provider_aggregate_proxy",
    "chain_verified": False,
    "wallet_buy_claim": False,
}


def _evidence_metadata(
    source: str, metadata: Mapping[str, object] | None,
) -> str:
    result = dict(metadata or {})
    if source == RANKS_KOL_SOURCE:
        for key, expected in _RANKS_ANNOTATIONS.items():
            if key in result and result[key] != expected:
                raise ValueError(f"ranks KOL metadata has invalid {key}")
            result[key] = expected
    return canonical_json(result)


class DecisionLedgerMixin:
    def record_kol_evidence(
        self,
        *,
        evidence_id: str,
        chain: str,
        token_address: str,
        signal_id: str,
        event_at: datetime,
        available_at: datetime,
        qualified_at: datetime,
        evidence_uri: str,
        source: str = OFFICIAL_KOL_SOURCE,
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[HistoricalKolEvidence]:
        now_us = self._now_us()
        event_us = to_us(event_at, "event_at")
        available_us = to_us(available_at, "available_at")
        qualified_us = to_us(qualified_at, "qualified_at")
        if not event_us <= available_us <= qualified_us:
            raise ValueError("KOL times must satisfy event <= available <= qualified")
        if qualified_us > now_us:
            raise ValueError("qualified_at must not be in the future")
        normalized_source = text(source, "source")
        if normalized_source not in KOL_SOURCES:
            raise ValueError("historical KOL evidence source is not allowlisted")
        identity = text(evidence_id, "evidence_id", 128)
        values = (
            identity, clean_chain(chain), token(token_address),
            text(signal_id, "signal_id", 128), event_us, available_us,
            qualified_us, normalized_source,
            text(evidence_uri, "evidence_uri", 2048),
            _evidence_metadata(normalized_source, metadata),
        )
        return self._append(
            table="v6_kol_evidence", key_column="evidence_id", key_value=identity,
            columns=_EVIDENCE_COLUMNS, values=values,
            label="KOL evidence", decode=rows.kol_evidence,
        )

    def kol_evidence(
        self, evidence_id: str, *, as_of: datetime | None = None,
    ) -> HistoricalKolEvidence | None:
        identity = text(evidence_id, "evidence_id", 128)
        if as_of is None:
            row = self._row(
                "SELECT * FROM v6_kol_evidence WHERE evidence_id = ?", (identity,),
            )
        else:
            cutoff = to_us(as_of, "as_of")
            row = self._row(
                "SELECT * FROM v6_kol_evidence WHERE evidence_id = ? "
                "AND available_at_us <= ? AND qualified_at_us <= ? "
                "AND inserted_at_us <= ?",
                (identity, cutoff, cutoff, cutoff),
            )
        return None if row is None else rows.kol_evidence(row)

    def eligible_historical_kol(
        self,
        *,
        current_signal_id: str,
        as_of: datetime,
        not_before_event_at: datetime | None = None,
    ) -> list[HistoricalKolEvidence]:
        cutoff = to_us(as_of, "as_of")
        current = self.signal(current_signal_id, as_of=as_of)
        if current is None:
            raise ValueError("current signal was not causally visible at as_of")
        active = self.current_signal(current.candidate_id, as_of=as_of)
        if active is None or active.signal_id != current.signal_id:
            raise ValueError("current_signal_id was not current at as_of")
        current_event = to_us(current.event_at, "current event_at")
        first_available = to_us(current.available_at, "current available_at")
        lower = (
            -9_223_372_036_854_775_808
            if not_before_event_at is None
            else to_us(not_before_event_at, "not_before_event_at")
        )
        result = self._rows(
            "SELECT * FROM v6_kol_evidence WHERE chain = ? "
            "AND token_address = ? AND source IN (?, ?) AND signal_id <> ? "
            "AND event_at_us >= ? AND event_at_us < ? "
            "AND available_at_us < ? AND qualified_at_us < ? "
            "AND commit_seq < ? AND available_at_us <= ? "
            "AND qualified_at_us <= ? AND inserted_at_us <= ? "
            "ORDER BY event_at_us DESC, qualified_at_us DESC, evidence_id DESC",
            (
                current.chain, current.token_address, OFFICIAL_KOL_SOURCE,
                RANKS_KOL_SOURCE, current.signal_id, lower, current_event, first_available,
                first_available, current.commit_seq, cutoff, cutoff, cutoff,
            ),
        )
        return [rows.kol_evidence(row) for row in result]

    def record_entry_decision(
        self,
        *,
        decision_id: str,
        candidate_id: str,
        signal_id: str,
        decided_at: datetime,
        status: str,
        reason: str,
        source: str,
        strategy_version: str,
        kol_evidence_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[EntryDecision]:
        now_us = self._now_us()
        decided_us = to_us(decided_at, "decided_at")
        if decided_us > now_us:
            raise ValueError("decided_at must not be in the future")
        identity = text(decision_id, "decision_id", 128)
        candidate_identity = text(candidate_id, "candidate_id", 128)
        signal_identity = text(signal_id, "signal_id", 128)
        evidence_identity = (
            None if kol_evidence_id is None
            else text(kol_evidence_id, "kol_evidence_id", 128)
        )
        values = (
            identity, candidate_identity, signal_identity, evidence_identity,
            decided_us, text(status, "status", 64).lower(),
            text(reason, "reason", 2048), text(source, "source"),
            text(strategy_version, "strategy_version", 128),
            canonical_json(metadata),
        )
        with self._write():
            result = self._append(
                table="v6_entry_decisions", key_column="decision_id",
                key_value=identity, columns=_DECISION_COLUMNS, values=values,
                label="entry decision", decode=rows.decision,
            )
            if not result.inserted:
                return result
            if self.candidate(candidate_identity, as_of=decided_at) is None:
                raise ValueError("candidate was not causally visible at decision time")
            current = self.current_signal(candidate_identity, as_of=decided_at)
            if current is None or current.signal_id != signal_identity:
                raise ValueError("signal was not current at decision time")
            if evidence_identity is not None:
                eligible = self.eligible_historical_kol(
                    current_signal_id=signal_identity, as_of=decided_at,
                )
                if evidence_identity not in {item.evidence_id for item in eligible}:
                    raise ValueError("KOL evidence was not historical at decision time")
            return result

    def entry_decision(self, decision_id: str) -> EntryDecision | None:
        identity = text(decision_id, "decision_id", 128)
        row = self._row(
            "SELECT * FROM v6_entry_decisions WHERE decision_id = ?", (identity,),
        )
        return None if row is None else rows.decision(row)
