"""Small source contracts consumed by the narrative collection application."""

from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Protocol

from ..debot.ranks_models import RankSnapshot
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .debot_feed import NarrativeDeBotCandidate
from .market_signal import MarketAnomaly
from .mint_location import MintLocation


class XSource(Protocol):
    def monitor_once(
        self, accept: Callable[[tuple[XPost, ...]], None] | None = None,
    ) -> tuple[XPost, ...]: ...


class TelegramSource(Protocol):
    def monitor_once(
        self, accept: Callable[[tuple[TelegramPost, ...]], None] | None = None,
    ) -> tuple[TelegramPost, ...]: ...


class DeBotSource(Protocol):
    def poll_once(
        self,
        *,
        anomaly: str | None = None,
        accept: Callable[[tuple[NarrativeDeBotCandidate, ...]], object] | None = None,
    ) -> tuple[NarrativeDeBotCandidate, ...]: ...


class MarketSource(Protocol):
    def poll_once(
        self,
        accept: Callable[[tuple[MarketAnomaly, ...]], object] | None = None,
    ) -> tuple[MarketAnomaly, ...]: ...


class MintSource(Protocol):
    def poll_once(
        self,
        accept: Callable[[tuple[RankSnapshot, ...]], object] | None = None,
    ) -> tuple[RankSnapshot, ...]: ...


class ChainMintSource(Protocol):
    poll_seconds: float

    def poll_once(
        self,
        accept: Callable[[tuple[MintLocation, ...]], object] | None = None,
    ) -> tuple[MintLocation, ...]: ...


class MintAlertDelivery(Protocol):
    poll_seconds: float

    def dispatch_once(self) -> object: ...


class TelegramRealtimeSource(Protocol):
    def run(
        self,
        stop: Event,
        accept: Callable[[tuple[object, ...]], None],
    ) -> None: ...


class RepostSource(Protocol):
    def poll_once(self) -> tuple[object, ...]: ...
