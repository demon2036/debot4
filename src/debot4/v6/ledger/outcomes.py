"""Canonical-chain-aware one-hour peak/final outcomes."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import localcontext

from . import rows
from .codec import ONE_HOUR_US, decimal_text, text, to_us
from .models import BlockObservation, InsertResult, OneHourResult, SimulatedBuy


_OUTCOME_COLUMNS = (
    "buy_id", "status", "reason", "window_ends_at_us", "cutoff_at_us",
    "coverage_complete_through_us", "allowed_lateness_us", "observation_count",
    "max_gap_us", "max_allowed_gap_us", "peak_fdv_usd",
    "peak_position_value_usd", "peak_observed_at_us", "peak_block_number",
    "final_fdv_usd", "final_position_value_usd", "final_observed_at_us",
    "final_block_number", "peak_multiple", "final_multiple", "peak_pnl_usd",
    "final_pnl_usd",
)


def _duration_us(value: timedelta, name: str) -> int:
    if not isinstance(value, timedelta):
        raise ValueError(f"{name} must be a timedelta")
    return (value.days * 86_400 + value.seconds) * 1_000_000 + value.microseconds


class OutcomeLedgerMixin:
    def _canonical_path(
        self, buy: SimulatedBuy, cutoff_us: int,
    ) -> tuple[str | None, str | None, list[BlockObservation]]:
        head = self._row(
            "SELECT * FROM v6_head_sightings WHERE buy_id = ? "
            "AND available_at_us <= ? AND inserted_at_us <= ? "
            "ORDER BY commit_seq DESC, sighting_id DESC LIMIT 1",
            (buy.buy_id, cutoff_us, cutoff_us),
        )
        if head is None:
            return "incomplete", "no_canonical_head", []
        observed = self._rows(
            "SELECT * FROM v6_block_observations WHERE buy_id = ? "
            "AND available_at_us <= ? AND inserted_at_us <= ?",
            (buy.buy_id, cutoff_us, cutoff_us),
        )
        by_hash = {str(row["block_hash"]): rows.observation(row) for row in observed}
        current = by_hash.get(str(head["block_hash"]))
        if current is None:
            return "incomplete", "canonical_chain_incomplete", []
        descending: list[BlockObservation] = []
        seen: set[str] = set()
        while True:
            if current.block_hash in seen:
                return "invalidated", "canonical_chain_invalid", []
            seen.add(current.block_hash)
            if current.block_number < buy.block_number:
                return "invalidated", "canonical_chain_invalid", []
            descending.append(current)
            if current.block_number == buy.block_number:
                if current.block_hash != buy.block_hash:
                    return "invalidated", "entry_block_reorged", []
                path = list(reversed(descending))
                times = [to_us(item.observed_at, "observed_at") for item in path]
                if any(right < left for left, right in zip(times, times[1:])):
                    return "invalidated", "canonical_chain_invalid", []
                return None, None, path
            parent = by_hash.get(current.parent_hash)
            if parent is None:
                return "incomplete", "canonical_chain_incomplete", []
            if parent.block_number != current.block_number - 1:
                return "invalidated", "canonical_chain_invalid", []
            current = parent

    def _complete_metrics(
        self, buy: SimulatedBuy, observations: list[BlockObservation],
    ) -> tuple[object, ...]:
        peak_fdv = buy.entry_fdv_usd
        peak_value = buy.entry_position_value_usd
        peak_time = to_us(buy.executed_at, "executed_at")
        peak_block = buy.block_number
        for observation in observations:
            if observation.fdv_usd > peak_fdv:
                peak_fdv = observation.fdv_usd
                peak_value = observation.position_value_usd
                peak_time = to_us(observation.observed_at, "observed_at")
                peak_block = observation.block_number
        final = observations[-1]
        with localcontext() as context:
            context.prec = 50
            multiples = (
                peak_value / buy.notional_usd,
                final.position_value_usd / buy.notional_usd,
            )
        return (
            decimal_text(peak_fdv), decimal_text(peak_value), peak_time, peak_block,
            decimal_text(final.fdv_usd), decimal_text(final.position_value_usd),
            to_us(final.observed_at, "observed_at"), final.block_number,
            decimal_text(multiples[0]), decimal_text(multiples[1]),
            decimal_text(peak_value - buy.notional_usd),
            decimal_text(final.position_value_usd - buy.notional_usd),
        )

    def finalize_one_hour(
        self,
        buy_id: str,
        *,
        as_of: datetime,
        coverage_complete_through: datetime,
        allowed_lateness: timedelta = timedelta(0),
        max_allowed_gap: timedelta = timedelta(minutes=5),
    ) -> InsertResult[OneHourResult]:
        identity = text(buy_id, "buy_id", 128)
        cutoff_us = to_us(as_of, "as_of")
        coverage_us = to_us(
            coverage_complete_through, "coverage_complete_through"
        )
        lateness_us = _duration_us(allowed_lateness, "allowed_lateness")
        allowed_gap_us = _duration_us(max_allowed_gap, "max_allowed_gap")
        if cutoff_us > self._now_us():
            raise ValueError("as_of must not be in the future")
        if lateness_us < 0:
            raise ValueError("allowed_lateness must be non-negative")
        if not 0 < allowed_gap_us <= ONE_HOUR_US:
            raise ValueError("max_allowed_gap must be within (0, 1h]")
        with self._write():
            existing = self._connection.execute(
                "SELECT * FROM v6_one_hour_results WHERE buy_id = ?", (identity,),
            ).fetchone()
            if existing is not None:
                return InsertResult(rows.outcome(existing), False)
            buy = self.buy(identity, as_of=as_of)
            if buy is None:
                raise ValueError("BUY was not causally visible at as_of")
            entry_us = to_us(buy.executed_at, "executed_at")
            window_end_us = entry_us + ONE_HOUR_US
            if cutoff_us < window_end_us + lateness_us:
                raise ValueError("configured allowed lateness has not elapsed")
            if not window_end_us <= coverage_us <= cutoff_us:
                raise ValueError(
                    "coverage watermark must cover the window and be visible at as_of"
                )
            chain_status, reason, path = self._canonical_path(buy, cutoff_us)
            observations = path[1:] if chain_status is None else []
            points = [entry_us]
            points.extend(to_us(item.observed_at, "observed_at") for item in observations)
            points.append(window_end_us)
            max_gap_us = max(right - left for left, right in zip(points, points[1:]))
            if chain_status is not None:
                status = chain_status
            elif not observations:
                status, reason = "incomplete", "no_post_entry_observation"
            elif max_gap_us > allowed_gap_us:
                status, reason = "incomplete", "coverage_gap_exceeded"
            else:
                status, reason = "complete", None
            metrics = (
                self._complete_metrics(buy, observations)
                if status == "complete" else (None,) * 12
            )
            values = (
                identity, status, reason, window_end_us, cutoff_us, coverage_us,
                lateness_us, len(observations), max_gap_us, allowed_gap_us, *metrics,
            )
            return self._append(
                table="v6_one_hour_results", key_column="buy_id",
                key_value=identity, columns=_OUTCOME_COLUMNS, values=values,
                label="one-hour result", decode=rows.outcome,
            )

    def outcome(
        self, buy_id: str, *, as_of: datetime | None = None,
    ) -> OneHourResult | None:
        identity = text(buy_id, "buy_id", 128)
        if as_of is None:
            row = self._row(
                "SELECT * FROM v6_one_hour_results WHERE buy_id = ?", (identity,),
            )
        else:
            cutoff = to_us(as_of, "as_of")
            row = self._row(
                "SELECT * FROM v6_one_hour_results WHERE buy_id = ? "
                "AND inserted_at_us <= ?", (identity, cutoff),
            )
        return None if row is None else rows.outcome(row)

    def due_buys(
        self, *, as_of: datetime, allowed_lateness: timedelta = timedelta(0),
    ) -> list[SimulatedBuy]:
        cutoff = to_us(as_of, "as_of")
        lateness_us = _duration_us(allowed_lateness, "allowed_lateness")
        if lateness_us < 0:
            raise ValueError("allowed_lateness must be non-negative")
        result = self._rows(
            "SELECT b.* FROM v6_simulated_buys AS b "
            "WHERE b.executed_at_us + ? + ? <= ? AND b.inserted_at_us <= ? "
            "AND NOT EXISTS (SELECT 1 FROM v6_one_hour_results AS r "
            "WHERE r.buy_id = b.buy_id AND r.inserted_at_us <= ?) "
            "ORDER BY b.executed_at_us, b.buy_id",
            (ONE_HOUR_US, lateness_us, cutoff, cutoff, cutoff),
        )
        return [rows.buy(row) for row in result]
