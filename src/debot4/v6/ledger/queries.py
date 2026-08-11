"""Small read projections needed by the live runtime."""

from __future__ import annotations

from datetime import datetime

from . import rows
from .codec import to_us
from .models import SimulatedBuy


class QueryLedgerMixin:
    def open_buys(self, *, as_of: datetime) -> list[SimulatedBuy]:
        cutoff = to_us(as_of, "as_of")
        result = self._rows(
            "SELECT b.* FROM v6_simulated_buys AS b "
            "WHERE b.executed_at_us <= ? AND b.inserted_at_us <= ? "
            "AND NOT EXISTS (SELECT 1 FROM v6_one_hour_results AS r "
            "WHERE r.buy_id = b.buy_id AND r.inserted_at_us <= ?) "
            "ORDER BY b.executed_at_us, b.buy_id",
            (cutoff, cutoff, cutoff),
        )
        return [rows.buy(row) for row in result]

    def has_signal(self, signal_id: str) -> bool:
        row = self._row(
            "SELECT 1 FROM v6_current_signals WHERE signal_id = ? LIMIT 1",
            (str(signal_id),),
        )
        return row is not None

    def table_counts(self) -> dict[str, int]:
        names = {
            "candidates": "v6_candidates",
            "signals": "v6_current_signals",
            "kol_evidence": "v6_kol_evidence",
            "decisions": "v6_entry_decisions",
            "buys": "v6_simulated_buys",
            "observations": "v6_block_observations",
            "head_sightings": "v6_head_sightings",
            "outcomes": "v6_one_hour_results",
        }
        return {
            key: int(self._row(f"SELECT COUNT(*) AS n FROM {table}", ())["n"])
            for key, table in names.items()
        }
