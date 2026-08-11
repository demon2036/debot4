"""Per-block executable position marking and immutable 1h settlement."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Event

from .config import AppConfig
from .events import EventLog
from .ledger import V6Ledger, V6LedgerFinalized
from .market import MarketQuoteEngine
from .state import RuntimeState


UTC = timezone.utc


class PositionTracker:
    def __init__(
        self,
        ledger: V6Ledger,
        market: MarketQuoteEngine,
        config: AppConfig,
        state: RuntimeState,
        events: EventLog,
    ) -> None:
        self.ledger = ledger
        self.market = market
        self.config = config
        self.state = state
        self.events = events
        self.last_block_hash: str | None = None

    def run(self, stop: Event) -> None:
        while not stop.is_set():
            try:
                self._tick()
            except Exception as exc:
                self.state.error(f"tracker: {type(exc).__name__}: {exc}")
                self.events.write("tracker_error", error=type(exc).__name__, detail=str(exc))
            stop.wait(self.config.runtime.mark_poll_seconds)

    def _tick(self) -> None:
        now = datetime.now(UTC)
        buys = self.ledger.open_buys(as_of=now)
        self.state.update(active_buys=len(buys))
        head = self.market.rpc.head()
        self.state.update(
            last_block_number=head.number,
            last_block_hash=head.block_hash,
            last_block_at=head.timestamp,
            last_head_fetch_at=head.fetched_at,
        )
        if head.block_hash != self.last_block_hash:
            self.last_block_hash = head.block_hash
            for buy in buys:
                if buy.executed_at < head.timestamp <= buy.window_ends_at:
                    self._mark(buy, head)
        for buy in self.ledger.due_buys(as_of=now):
            result = self.ledger.finalize_one_hour(
                buy.buy_id, as_of=now,
                max_allowed_gap=timedelta(
                    seconds=self.config.strategy.max_observation_gap_seconds
                ),
            )
            if result.inserted:
                self.state.increment("completed_outcomes")
                self.events.write(
                    "one_hour_finalized", buy_id=buy.buy_id,
                    status=result.record.status,
                    peak_multiple=result.record.peak_multiple,
                    final_pnl_usd=result.record.final_pnl_usd,
                    reason=result.record.reason,
                )

    def _mark(self, buy: object, head: object) -> None:
        metadata = getattr(buy, "metadata")
        pair = str(metadata.get("pair_address") or "")
        tokens = int(metadata.get("tokens_received_raw") or 0)
        sell_tax = Decimal(str(metadata.get("sell_tax_pct") or 0))
        if not pair or tokens <= 0:
            self.events.write("mark_rejected", buy_id=buy.buy_id, reason="missing_fill_metadata")
            return
        try:
            mark = self.market.mark(
                buy.token_address, pair, tokens_received_raw=tokens,
                sell_tax_pct=sell_tax, head=head,
            )
            result = self.ledger.record_block_observation(
                buy_id=buy.buy_id, block_number=head.number,
                block_hash=head.block_hash, observed_at=head.timestamp,
                available_at=datetime.now(UTC), fdv_usd=mark.fdv_usd,
                position_value_usd=mark.exit_value_usd,
                source="bsc:pancake-v2:fixed-block",
                evidence_uri=f"bsc://block/{head.number}/{head.block_hash}",
                metadata={"pair_address": pair, "quote_address": mark.state.quote_address},
            )
            if result.inserted:
                self.events.write(
                    "position_mark", buy_id=buy.buy_id, block_number=head.number,
                    fdv_usd=mark.fdv_usd, exit_value_usd=mark.exit_value_usd,
                )
        except V6LedgerFinalized:
            return
        except Exception as exc:
            self.state.error(f"mark {buy.buy_id}: {type(exc).__name__}: {exc}")
            self.events.write(
                "mark_error", buy_id=buy.buy_id, block_number=head.number,
                error=type(exc).__name__, detail=str(exc),
            )
