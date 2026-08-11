"""Atomic simulated BUY creation and immutable block facts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib

from . import rows
from .codec import (
    ONE_HOUR_US,
    V6LedgerFinalized,
    block_hash as clean_block_hash,
    block_number as clean_block_number,
    canonical_json,
    decimal_text,
    decimal_value,
    text,
    to_us,
)
from .models import BlockObservation, InsertResult, SimulatedBuy, SimulatedBuyCommit


_BUY_COLUMNS = (
    "buy_id", "decision_id", "candidate_id", "signal_id", "chain",
    "token_address", "executed_at_us", "block_number", "block_hash",
    "entry_fdv_usd", "notional_usd", "entry_position_value_usd", "source",
    "evidence_uri", "metadata_json",
)
_OBSERVATION_COLUMNS = (
    "observation_id", "buy_id", "block_number", "block_hash", "parent_hash",
    "observed_at_us", "available_at_us", "fdv_usd", "position_value_usd",
    "source", "evidence_uri", "metadata_json",
)


def _observation_id(buy_id: str, block_hash: str) -> str:
    return hashlib.sha256(f"{buy_id}\0{block_hash}".encode()).hexdigest()


class TradeLedgerMixin:
    def _record_buy(
        self,
        *,
        buy_id: str,
        decision_id: str,
        candidate_id: str,
        signal_id: str,
        executed_at: datetime,
        block_number: int,
        block_hash: str,
        entry_fdv_usd: object,
        notional_usd: object,
        entry_position_value_usd: object,
        source: str,
        evidence_uri: str,
        metadata: Mapping[str, object] | None,
    ) -> InsertResult[SimulatedBuy]:
        now_us = self._now_us()
        executed_us = to_us(executed_at, "executed_at")
        if executed_us > now_us:
            raise ValueError("executed_at must not be in the future")
        identity = text(buy_id, "buy_id", 128)
        decision_identity = text(decision_id, "decision_id", 128)
        candidate_identity = text(candidate_id, "candidate_id", 128)
        signal_identity = text(signal_id, "signal_id", 128)
        number = clean_block_number(block_number)
        block = clean_block_hash(block_hash)
        decision = self.entry_decision(decision_identity)
        candidate = self.candidate(candidate_identity)
        if decision is None or candidate is None:
            raise ValueError("BUY requires an existing decision and candidate")
        values = (
            identity, decision_identity, candidate_identity, signal_identity,
            candidate.chain, candidate.token_address, executed_us, number, block,
            decimal_text(decimal_value(entry_fdv_usd, "entry_fdv_usd", positive=True)),
            decimal_text(decimal_value(notional_usd, "notional_usd", positive=True)),
            decimal_text(decimal_value(
                entry_position_value_usd, "entry_position_value_usd", positive=True,
            )),
            text(source, "source"), text(evidence_uri, "evidence_uri", 2048),
            canonical_json(metadata),
        )
        with self._write():
            result = self._append(
                table="v6_simulated_buys", key_column="buy_id",
                key_value=identity, columns=_BUY_COLUMNS, values=values,
                label="simulated BUY", decode=rows.buy,
            )
            if not result.inserted:
                return result
            if decision.status != "buy":
                raise ValueError("simulated BUY requires a buy decision")
            if (
                decision.candidate_id != candidate_identity
                or decision.signal_id != signal_identity
            ):
                raise ValueError("BUY identities do not match its decision")
            if to_us(decision.decided_at, "decided_at") > executed_us:
                raise ValueError("BUY cannot execute before its decision")
            return result

    def commit_simulated_buy(
        self,
        *,
        buy_id: str,
        decision_id: str,
        candidate_id: str,
        signal_id: str,
        decided_at: datetime,
        executed_at: datetime,
        reason: str,
        strategy_version: str,
        block_number: int,
        block_hash: str,
        parent_block_hash: str,
        entry_fdv_usd: object,
        notional_usd: object,
        entry_position_value_usd: object,
        source: str,
        evidence_uri: str,
        kol_evidence_id: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> SimulatedBuyCommit:
        with self._write():
            decision = self.record_entry_decision(
                decision_id=decision_id, candidate_id=candidate_id,
                signal_id=signal_id, kol_evidence_id=kol_evidence_id,
                decided_at=decided_at, status="buy", reason=reason,
                source=source, strategy_version=strategy_version,
                metadata=metadata,
            )
            buy = self._record_buy(
                buy_id=buy_id, decision_id=decision_id,
                candidate_id=candidate_id, signal_id=signal_id,
                executed_at=executed_at, block_number=block_number,
                block_hash=block_hash, entry_fdv_usd=entry_fdv_usd,
                notional_usd=notional_usd,
                entry_position_value_usd=entry_position_value_usd,
                source=source, evidence_uri=evidence_uri, metadata=metadata,
            )
            entry = self.commit_canonical_observation(
                buy_id=buy_id, block_number=block_number, block_hash=block_hash,
                parent_hash=parent_block_hash, observed_at=executed_at,
                available_at=executed_at, fdv_usd=entry_fdv_usd,
                position_value_usd=entry_position_value_usd,
                source=source, evidence_uri=evidence_uri, metadata=metadata,
            )
            return SimulatedBuyCommit(decision, buy, entry)

    def buy(
        self, buy_id: str, *, as_of: datetime | None = None,
    ) -> SimulatedBuy | None:
        identity = text(buy_id, "buy_id", 128)
        if as_of is None:
            row = self._row(
                "SELECT * FROM v6_simulated_buys WHERE buy_id = ?", (identity,),
            )
        else:
            cutoff = to_us(as_of, "as_of")
            row = self._row(
                "SELECT * FROM v6_simulated_buys WHERE buy_id = ? "
                "AND executed_at_us <= ? AND inserted_at_us <= ?",
                (identity, cutoff, cutoff),
            )
        return None if row is None else rows.buy(row)

    def record_block_observation(
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
        metadata: Mapping[str, object] | None = None,
    ) -> InsertResult[BlockObservation]:
        now_us = self._now_us()
        buy_identity = text(buy_id, "buy_id", 128)
        number = clean_block_number(block_number)
        block = clean_block_hash(block_hash)
        parent = clean_block_hash(parent_hash)
        if block == parent:
            raise ValueError("block_hash and parent_hash must differ")
        observed_us = to_us(observed_at, "observed_at")
        available_us = to_us(available_at, "available_at")
        if not observed_us <= available_us <= now_us:
            raise ValueError("observation times must satisfy observed <= available <= now")
        identity = _observation_id(buy_identity, block)
        values = (
            identity, buy_identity, number, block, parent, observed_us, available_us,
            decimal_text(decimal_value(fdv_usd, "fdv_usd", positive=True)),
            decimal_text(decimal_value(
                position_value_usd, "position_value_usd", positive=True,
            )),
            text(source, "source"), text(evidence_uri, "evidence_uri", 2048),
            canonical_json(metadata),
        )
        with self._write():
            existing = self._connection.execute(
                "SELECT 1 FROM v6_block_observations WHERE observation_id = ?",
                (identity,),
            ).fetchone()
            if existing is None and self._connection.execute(
                "SELECT 1 FROM v6_one_hour_results WHERE buy_id = ?",
                (buy_identity,),
            ).fetchone() is not None:
                raise V6LedgerFinalized("one-hour result is already finalized")
            result = self._append(
                table="v6_block_observations", key_column="observation_id",
                key_value=identity, columns=_OBSERVATION_COLUMNS, values=values,
                label="block observation", decode=rows.observation,
            )
            if not result.inserted:
                return result
            buy = self.buy(buy_identity)
            if buy is None:
                raise ValueError(f"unknown BUY {buy_identity!r}")
            entry_us = to_us(buy.executed_at, "executed_at")
            if not entry_us <= observed_us <= entry_us + ONE_HOUR_US:
                raise ValueError("observation lies outside the 0-1h window")
            if number < buy.block_number:
                raise ValueError("observation block precedes the entry block")
            return result

    def observations_for_buy(
        self, buy_id: str, *, as_of: datetime | None = None,
    ) -> list[BlockObservation]:
        identity = text(buy_id, "buy_id", 128)
        values: tuple[object, ...] = (identity,)
        visible = ""
        if as_of is not None:
            cutoff = to_us(as_of, "as_of")
            visible = " AND available_at_us <= ? AND inserted_at_us <= ?"
            values = (identity, cutoff, cutoff)
        result = self._rows(
            "SELECT * FROM v6_block_observations WHERE buy_id = ?" + visible
            + " ORDER BY observed_at_us, block_number, commit_seq, block_hash",
            values,
        )
        return [rows.observation(row) for row in result]
