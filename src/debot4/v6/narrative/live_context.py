"""Normalized DeBot context consumed by the v6 narrative classifier."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from ..domain import DeBotSignal
from .models import aware_utc


@dataclass(frozen=True, slots=True)
class DeBotNarrativeContext:
    token_address: str
    signal_id: str
    signal_kind: str
    group_name: str
    event_at: datetime
    available_at: datetime
    token_name: str | None
    token_symbol: str | None
    description: str | None
    narrative_urls: tuple[str, ...]
    wallet_aliases: tuple[str, ...]
    kol_buy_qualified: bool
    kol_buy_reason: str
    raw_context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        token = self.token_address.strip().lower()
        signal_id = self.signal_id.strip()
        kind = self.signal_kind.strip().lower()
        group = self.group_name.strip()
        event = aware_utc(self.event_at, "event_at")
        available = aware_utc(self.available_at, "available_at")
        if not signal_id or not token.startswith("0x") or len(token) != 42:
            raise ValueError("exact token and signal identity are required")
        if kind not in {"kol", "smart_money"} or not group:
            raise ValueError("supported DeBot signal kind and group are required")
        if event > available:
            raise ValueError("event_at cannot be after available_at")
        if not isinstance(self.kol_buy_qualified, bool):
            raise ValueError("kol_buy_qualified must be boolean")
        object.__setattr__(self, "token_address", token)
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "signal_kind", kind)
        object.__setattr__(self, "group_name", group)
        object.__setattr__(self, "event_at", event)
        object.__setattr__(self, "available_at", available)
        object.__setattr__(self, "narrative_urls", tuple(self.narrative_urls))
        object.__setattr__(self, "wallet_aliases", tuple(self.wallet_aliases))

    @classmethod
    def from_signal(cls, signal: DeBotSignal) -> "DeBotNarrativeContext":
        return cls(
            token_address=signal.token_address,
            signal_id=signal.signal_id,
            signal_kind=signal.signal_kind,
            group_name=signal.group_name,
            event_at=signal.event_at,
            available_at=signal.available_at,
            token_name=signal.token_name,
            token_symbol=signal.token_symbol,
            description=signal.description,
            narrative_urls=signal.narrative_urls,
            wallet_aliases=tuple(item.alias for item in signal.wallet_trades),
            kol_buy_qualified=signal.kol_buy_qualified,
            kol_buy_reason=signal.kol_buy_reason,
            raw_context=signal.raw_context,
        )
