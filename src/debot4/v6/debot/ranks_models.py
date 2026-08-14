"""Immutable records for DeBot's BSC meme-ranks feed."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class RankSnapshot:
    token_address: str
    stage: str
    fetched_at: datetime
    name: str | None
    symbol: str | None
    kols: int
    kol_aliases: tuple[str, ...]
    kol_holds: Decimal | None
    provider_fdv_usd: Decimal | None
    launched: bool
    created_at: datetime | None = None
    launchpad: str | None = None
    description: str | None = None
    social_urls: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RankPage:
    stage: str
    snapshots: tuple[RankSnapshot, ...]
    fetched_at: datetime
    bytes_read: int


@dataclass(frozen=True, slots=True)
class RankKolIncrease:
    snapshot: RankSnapshot
    previous_kols: int
    previous_aliases: tuple[str, ...]

    @property
    def increase(self) -> int:
        return self.snapshot.kols - self.previous_kols
