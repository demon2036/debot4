"""Point-in-time, read-only matching of DEX leaders to the v6 ledger."""

from __future__ import annotations

from pathlib import Path
import sqlite3

from .models import Coverage, CoverageBatch, Gainer


class CoverageReader:
    def __init__(self, ledger_database: str | Path) -> None:
        self.path = Path(ledger_database)

    def read(self, rows: tuple[Gainer, ...], *, as_of_us: int) -> CoverageBatch:
        if not self.path.exists():
            return self._unavailable(rows, "v6 ledger file does not exist")
        try:
            connection = sqlite3.connect(
                f"file:{self.path}?mode=ro", uri=True, timeout=2
            )
            connection.row_factory = sqlite3.Row
            try:
                covered = tuple(
                    self._token(connection, row.token_address, as_of_us) for row in rows
                )
            finally:
                connection.close()
        except sqlite3.Error as exc:
            return self._unavailable(rows, f"ledger read failed: {str(exc)[:160]}")
        return CoverageBatch(True, None, covered)

    @staticmethod
    def _token(
        connection: sqlite3.Connection, token_address: str, as_of_us: int
    ) -> Coverage:
        token = token_address.lower()
        signal = connection.execute(
            "SELECT signal_id, event_at_us FROM v6_current_signals "
            "WHERE lower(chain)='bsc' AND lower(token_address)=? "
            "AND available_at_us<=? AND inserted_at_us<=? "
            "ORDER BY event_at_us DESC, signal_id DESC LIMIT 1",
            (token, as_of_us, as_of_us),
        ).fetchone()
        decision = connection.execute(
            "SELECT d.decision_id, d.decided_at_us, d.status "
            "FROM v6_entry_decisions d JOIN v6_current_signals s "
            "ON s.signal_id=d.signal_id WHERE lower(s.chain)='bsc' "
            "AND lower(s.token_address)=? AND s.available_at_us<=? "
            "AND s.inserted_at_us<=? AND d.decided_at_us<=? "
            "AND d.inserted_at_us<=? "
            "ORDER BY d.decided_at_us DESC, d.decision_id DESC LIMIT 1",
            (token, as_of_us, as_of_us, as_of_us, as_of_us),
        ).fetchone()
        buy = connection.execute(
            "SELECT buy_id, executed_at_us FROM v6_simulated_buys "
            "WHERE lower(chain)='bsc' AND lower(token_address)=? "
            "AND executed_at_us<=? AND inserted_at_us<=? "
            "ORDER BY executed_at_us DESC, buy_id DESC LIMIT 1",
            (token, as_of_us, as_of_us),
        ).fetchone()
        reason = _miss_reason(signal, decision, buy)
        return Coverage(
            token_address=token,
            discovered=signal is not None,
            signal_id=None if signal is None else str(signal["signal_id"]),
            signal_at_us=None if signal is None else int(signal["event_at_us"]),
            decided=decision is not None,
            decision_id=None if decision is None else str(decision["decision_id"]),
            decision_at_us=None if decision is None else int(decision["decided_at_us"]),
            decision_status=None if decision is None else str(decision["status"]),
            bought=buy is not None,
            buy_id=None if buy is None else str(buy["buy_id"]),
            buy_at_us=None if buy is None else int(buy["executed_at_us"]),
            miss_reason=reason,
        )

    @staticmethod
    def _unavailable(rows: tuple[Gainer, ...], reason: str) -> CoverageBatch:
        return CoverageBatch(
            False,
            reason,
            tuple(
                Coverage(row.token_address, miss_reason="coverage_unavailable")
                for row in rows
            ),
        )


def _miss_reason(
    signal: sqlite3.Row | None,
    decision: sqlite3.Row | None,
    buy: sqlite3.Row | None,
) -> str:
    if buy is not None:
        return "covered_by_buy"
    if decision is not None:
        status = str(decision["status"]).strip().lower() or "unknown"
        return "buy_decision_not_executed" if status == "buy" else f"decision_{status}"
    if signal is not None:
        return "signal_without_decision"
    return "not_discovered_by_debot"
