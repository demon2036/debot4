"""Candidate discovery and append-only current-signal projections."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from . import rows
from .codec import canonical_json, chain as clean_chain, text, to_us, token
from .models import Candidate, CandidateSignalCommit, CurrentSignal, InsertResult


_CANDIDATE_COLUMNS = (
    "candidate_id", "chain", "token_address", "detected_at_us",
    "available_at_us", "source", "evidence_uri", "metadata_json",
)
_SIGNAL_COLUMNS = (
    "signal_id", "candidate_id", "chain", "token_address", "event_at_us",
    "available_at_us", "signal_kind", "source", "evidence_uri", "metadata_json",
)


class SignalLedgerMixin:
    def record_candidate(
        self,
        *,
        candidate_id: str,
        chain: str,
        token_address: str,
        detected_at: datetime,
        available_at: datetime,
        source: str,
        evidence_uri: str,
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[Candidate]:
        now_us = self._now_us()
        detected_us = to_us(detected_at, "detected_at")
        available_us = to_us(available_at, "available_at")
        if detected_us > available_us:
            raise ValueError("detected_at must not follow available_at")
        if available_us > now_us:
            raise ValueError("available_at must not be in the future")
        identity = text(candidate_id, "candidate_id", 128)
        values = (
            identity, clean_chain(chain), token(token_address), detected_us,
            available_us, text(source, "source"),
            text(evidence_uri, "evidence_uri", 2048), canonical_json(metadata),
        )
        return self._append(
            table="v6_candidates", key_column="candidate_id", key_value=identity,
            columns=_CANDIDATE_COLUMNS, values=values,
            label="candidate", decode=rows.candidate,
        )

    def candidate(
        self, candidate_id: str, *, as_of: datetime | None = None,
    ) -> Candidate | None:
        identity = text(candidate_id, "candidate_id", 128)
        if as_of is None:
            row = self._row(
                "SELECT * FROM v6_candidates WHERE candidate_id = ?", (identity,),
            )
        else:
            cutoff = to_us(as_of, "as_of")
            row = self._row(
                "SELECT * FROM v6_candidates WHERE candidate_id = ? "
                "AND available_at_us <= ? AND inserted_at_us <= ?",
                (identity, cutoff, cutoff),
            )
        return None if row is None else rows.candidate(row)

    def record_current_signal(
        self,
        *,
        signal_id: str,
        candidate_id: str,
        event_at: datetime,
        available_at: datetime,
        signal_kind: str,
        source: str,
        evidence_uri: str,
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[CurrentSignal]:
        now_us = self._now_us()
        event_us = to_us(event_at, "event_at")
        available_us = to_us(available_at, "available_at")
        if event_us > available_us:
            raise ValueError("event_at must not follow available_at")
        if available_us > now_us:
            raise ValueError("available_at must not be in the future")
        identity = text(signal_id, "signal_id", 128)
        candidate_identity = text(candidate_id, "candidate_id", 128)
        with self._write():
            candidate_row = self._connection.execute(
                "SELECT * FROM v6_candidates WHERE candidate_id = ?",
                (candidate_identity,),
            ).fetchone()
            if candidate_row is None:
                raise ValueError(f"unknown candidate {candidate_identity!r}")
            values = (
                identity, candidate_identity, str(candidate_row["chain"]),
                str(candidate_row["token_address"]), event_us, available_us,
                text(signal_kind, "signal_kind", 128), text(source, "source"),
                text(evidence_uri, "evidence_uri", 2048), canonical_json(metadata),
            )
            return self._append(
                table="v6_current_signals", key_column="signal_id",
                key_value=identity, columns=_SIGNAL_COLUMNS, values=values,
                label="signal", decode=rows.signal,
            )

    def signal(
        self, signal_id: str, *, as_of: datetime | None = None,
    ) -> CurrentSignal | None:
        identity = text(signal_id, "signal_id", 128)
        if as_of is None:
            row = self._row(
                "SELECT * FROM v6_current_signals WHERE signal_id = ?", (identity,),
            )
        else:
            cutoff = to_us(as_of, "as_of")
            row = self._row(
                "SELECT * FROM v6_current_signals WHERE signal_id = ? "
                "AND available_at_us <= ? AND inserted_at_us <= ?",
                (identity, cutoff, cutoff),
            )
        return None if row is None else rows.signal(row)

    def current_signal(
        self, candidate_id: str, *, as_of: datetime,
    ) -> CurrentSignal | None:
        identity = text(candidate_id, "candidate_id", 128)
        cutoff = to_us(as_of, "as_of")
        row = self._row(
            "SELECT * FROM v6_current_signals WHERE candidate_id = ? "
            "AND available_at_us <= ? AND inserted_at_us <= ? "
            "ORDER BY event_at_us DESC, available_at_us DESC, "
            "inserted_at_us DESC, signal_id DESC LIMIT 1",
            (identity, cutoff, cutoff),
        )
        return None if row is None else rows.signal(row)

    def record_candidate_with_signal(
        self,
        *,
        candidate_id: str,
        chain: str,
        token_address: str,
        detected_at: datetime,
        candidate_available_at: datetime,
        signal_id: str,
        signal_event_at: datetime,
        signal_available_at: datetime,
        signal_kind: str,
        source: str,
        evidence_uri: str,
        candidate_metadata: Mapping[str, object] | None = None,
        signal_metadata: Mapping[str, object] | None = None,
    ) -> CandidateSignalCommit:
        with self._write():
            candidate_result = self.record_candidate(
                candidate_id=candidate_id, chain=chain, token_address=token_address,
                detected_at=detected_at, available_at=candidate_available_at,
                source=source, evidence_uri=evidence_uri,
                metadata=candidate_metadata,
            )
            signal_result = self.record_current_signal(
                signal_id=signal_id, candidate_id=candidate_id,
                event_at=signal_event_at, available_at=signal_available_at,
                signal_kind=signal_kind, source=source, evidence_uri=evidence_uri,
                metadata=signal_metadata,
            )
            return CandidateSignalCommit(candidate_result, signal_result)
