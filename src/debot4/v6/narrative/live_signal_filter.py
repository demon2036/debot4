"""Cheap, deterministic filtering before expensive narrative research."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import re
from typing import Protocol

from ..domain import DeBotSignal
from ..identity import utc_datetime, utc_now
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .actors import ActorRef, ActorTier
from .market_signal import MarketAnomaly


NarrativeSignal = XPost | TelegramPost | DeBotSignal | MarketAnomaly
_BSC_ECOSYSTEMS = frozenset({"bsc", "bnb", "binance", "robinhood"})
_ACTION = re.compile(
    r"(?:\b(?:ca|contract|mint|launch(?:ed|ing)?|deploy(?:ed|ment)?|"
    r"list(?:ed|ing)?|liquidity|burn(?:ed|ing)?|migrat(?:e|ed|ion)|"
    r"buy|bought|ape|airdrop|ticker)\b|"
    r"\$[A-Za-z][A-Za-z0-9]{1,14}\b|"
    r"合约|地址|买入|上线|开盘|发射|部署|迁移|空投)",
    re.IGNORECASE,
)
_LAUNCHPAD = re.compile(
    r"(?:four\.meme|fourmeme|flap\.sh|debot\.ai|dexscreener|"
    r"pancakeswap|gmgn\.ai)",
    re.IGNORECASE,
)
_BSC_CONTEXT = re.compile(
    r"(?:\b(?:bsc|bnb(?:\s+chain)?|binance|pancakeswap)\b|"
    r"four\.meme|fourmeme|flap\.sh)",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class SignalFilterDecision:
    accepted: bool
    reason: str


class NarrativeSignalFilter(Protocol):
    def decide(self, signal: NarrativeSignal) -> SignalFilterDecision: ...


class AllowAllSignalFilter:
    """Explicit compatibility policy for isolated collectors and tests."""

    def decide(self, signal: NarrativeSignal) -> SignalFilterDecision:
        del signal
        return SignalFilterDecision(True, "unfiltered")


class BscRealtimeSignalFilter:
    """Keep upstream catalysts and exact/fresh BSC leads; drop routine chatter."""

    def __init__(
        self,
        registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
        *,
        clock=utc_now,
        debot_fresh_seconds: float = 180.0,
        x_fresh_seconds: float = 300.0,
    ) -> None:
        if not 1 <= float(debot_fresh_seconds) <= 900:
            raise ValueError("DeBot freshness must be between 1 and 900 seconds")
        if not 1 <= float(x_fresh_seconds) <= 900:
            raise ValueError("X freshness must be between 1 and 900 seconds")
        self.registry = registry
        self.clock = clock
        self.debot_freshness = timedelta(seconds=float(debot_fresh_seconds))
        self.x_freshness = timedelta(seconds=float(x_fresh_seconds))

    def decide(self, signal: NarrativeSignal) -> SignalFilterDecision:
        if isinstance(signal, XPost):
            return self._x(signal)
        if isinstance(signal, TelegramPost):
            return self._telegram(signal)
        if isinstance(signal, DeBotSignal):
            return self._debot(signal)
        if isinstance(signal, MarketAnomaly):
            return SignalFilterDecision(True, "exact_market_anomaly")
        raise TypeError("unsupported narrative signal")

    def _x(self, post: XPost) -> SignalFilterDecision:
        if not _is_fresh(
            utc_datetime(self.clock()),
            post.created_at,
            post.fetched_at,
            self.x_freshness,
        ):
            return SignalFilterDecision(False, "stale_x_replay")
        if post.bsc_contracts:
            return SignalFilterDecision(True, "exact_bsc_ca")
        actor = self.registry.resolve(post.author)
        if actor.tier is ActorTier.GLOBAL_AGENDA:
            return SignalFilterDecision(True, "global_agenda_event")
        if actor.can_establish_origin or actor.can_create_catalyst:
            return SignalFilterDecision(True, "reviewed_catalyst_event")
        content = (post.text, post.target_text, *post.urls)
        if (
            self._bsc_actor(actor)
            and _actionable(*content)
            and _bsc_context(*content)
        ):
            return SignalFilterDecision(True, "bsc_actor_actionable")
        return SignalFilterDecision(False, "routine_x_chatter")

    def _telegram(self, post: TelegramPost) -> SignalFilterDecision:
        if post.bsc_contracts:
            return SignalFilterDecision(True, "exact_bsc_ca")
        actor = self.registry.resolve_telegram(post.channel)
        if actor is not None and (
            actor.can_establish_origin or actor.can_create_catalyst
        ):
            return SignalFilterDecision(True, "reviewed_catalyst_event")
        content = (post.text, *post.urls)
        if (
            actor is not None
            and self._bsc_actor(actor)
            and (post.has_media or _actionable(*content))
            and _bsc_context(*content)
        ):
            return SignalFilterDecision(True, "bsc_channel_actionable")
        return SignalFilterDecision(False, "routine_telegram_chatter")

    def _debot(self, signal: DeBotSignal) -> SignalFilterDecision:
        now = utc_datetime(self.clock())
        fresh = _is_fresh(
            now,
            signal.event_at,
            signal.available_at,
            self.debot_freshness,
        )
        if signal.kol_buy_qualified and fresh:
            return SignalFilterDecision(True, "qualified_debot_kol")
        kind = signal.signal_kind.strip().casefold().replace("-", "_")
        group = signal.group_name.split("#", 1)[0].strip().casefold()
        recognized = (
            kind in {"kol", "smart_money", "smartmoney"}
            or group in {"kol", "smartmoney", "smart_money"}
        )
        if recognized and fresh:
            return SignalFilterDecision(True, "fresh_debot_token_lead")
        return SignalFilterDecision(False, "stale_or_unqualified_debot")

    @staticmethod
    def _bsc_actor(actor: ActorRef) -> bool:
        return bool(_BSC_ECOSYSTEMS.intersection(actor.ecosystems))


def _actionable(*values: str) -> bool:
    text = " ".join(item for item in values if item)
    return bool(_ACTION.search(text) or _LAUNCHPAD.search(text))


def _bsc_context(*values: str) -> bool:
    text = " ".join(item for item in values if item)
    return bool(_BSC_CONTEXT.search(text))


def _is_fresh(now, event_at, available_at, window: timedelta) -> bool:
    tolerance = timedelta(seconds=30)
    event_age = now - utc_datetime(event_at)
    availability_age = now - utc_datetime(available_at)
    return (
        -tolerance <= event_age <= window
        and -tolerance <= availability_age <= window
    )


__all__ = [
    "AllowAllSignalFilter",
    "BscRealtimeSignalFilter",
    "NarrativeSignal",
    "NarrativeSignalFilter",
    "SignalFilterDecision",
]
