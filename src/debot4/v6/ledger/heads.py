"""Append-only canonical-head sightings layered over immutable block facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib

from . import rows
from .codec import (
    V6LedgerFinalized,
    block_hash as clean_block_hash,
    block_number as clean_block_number,
    canonical_json,
    text,
    to_us,
)
from .models import (
    CanonicalHeadSighting,
    CanonicalObservationCommit,
    InsertResult,
)


_HEAD_COLUMNS = (
    "sighting_id", "buy_id", "block_number", "block_hash", "sighted_at_us",
    "available_at_us", "source", "evidence_uri", "metadata_json",
)


def _sighting_id(buy_id: str, block_hash: str, sighted_at_us: int) -> str:
    payload = f"{buy_id}\0{block_hash}\0{sighted_at_us}".encode()
    return hashlib.sha256(payload).hexdigest()


class HeadLedgerMixin:
    def record_head_sighting(
        self,
        *,
        buy_id: str,
        block_number: int,
        block_hash: str,
        sighted_at: datetime,
        available_at: datetime,
        source: str,
        evidence_uri: str,
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[CanonicalHeadSighting]:
        now_us = self._now_us()
        buy_identity = text(buy_id, "buy_id", 128)
        number = clean_block_number(block_number)
        block = clean_block_hash(block_hash)
        sighted_us = to_us(sighted_at, "sighted_at")
        available_us = to_us(available_at, "available_at")
        if not sighted_us <= available_us <= now_us:
            raise ValueError("head times must satisfy sighted <= available <= now")
        identity = _sighting_id(buy_identity, block, sighted_us)
        values = (
            identity, buy_identity, number, block, sighted_us, available_us,
            text(source, "source"), text(evidence_uri, "evidence_uri", 2048),
            canonical_json(metadata),
        )
        with self._write():
            existing = self._connection.execute(
                "SELECT 1 FROM v6_head_sightings WHERE sighting_id = ?",
                (identity,),
            ).fetchone()
            if existing is None and self._connection.execute(
                "SELECT 1 FROM v6_one_hour_results WHERE buy_id = ?",
                (buy_identity,),
            ).fetchone() is not None:
                raise V6LedgerFinalized("one-hour result is already finalized")
            observed = self._connection.execute(
                "SELECT 1 FROM v6_block_observations "
                "WHERE buy_id = ? AND block_number = ? AND block_hash = ?",
                (buy_identity, number, block),
            ).fetchone()
            if observed is None:
                raise ValueError("canonical head must reference an observed block")
            return self._append(
                table="v6_head_sightings", key_column="sighting_id",
                key_value=identity, columns=_HEAD_COLUMNS, values=values,
                label="canonical head sighting", decode=rows.head_sighting,
            )

    def commit_canonical_observation(
        self,
        *,
        buy_id: str,
        block_number: int,
        block_hash: str,
        parent_hash: str,
        observed_at: datetime,
        available_at: datetime,
        fdv_usd: object,
        position_value_usd: object,
        source: str,
        evidence_uri: str,
        sighted_at: datetime | None = None,
        head_available_at: datetime | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> CanonicalObservationCommit:
        with self._write():
            observation = self.record_block_observation(
                buy_id=buy_id, block_number=block_number, block_hash=block_hash,
                parent_hash=parent_hash, observed_at=observed_at,
                available_at=available_at, fdv_usd=fdv_usd,
                position_value_usd=position_value_usd, source=source,
                evidence_uri=evidence_uri, metadata=metadata,
            )
            head = self.record_head_sighting(
                buy_id=buy_id, block_number=block_number, block_hash=block_hash,
                sighted_at=sighted_at or available_at,
                available_at=head_available_at or available_at,
                source=source, evidence_uri=evidence_uri, metadata=metadata,
            )
            return CanonicalObservationCommit(observation, head)

    def head_sightings_for_buy(
        self, buy_id: str, *, as_of: datetime | None = None,
    ) -> list[CanonicalHeadSighting]:
        identity = text(buy_id, "buy_id", 128)
        values: tuple[object, ...] = (identity,)
        visible = ""
        if as_of is not None:
            cutoff = to_us(as_of, "as_of")
            visible = " AND available_at_us <= ? AND inserted_at_us <= ?"
            values = (identity, cutoff, cutoff)
        result = self._rows(
            "SELECT * FROM v6_head_sightings WHERE buy_id = ?" + visible
            + " ORDER BY commit_seq, sighting_id",
            values,
        )
        return [rows.head_sighting(row) for row in result]
