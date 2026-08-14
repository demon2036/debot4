"""One-way orchestration of active and passive narrative research."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime
from typing import Protocol

from ..domain import DeBotSignal
from ..identity import utc_now
from ..telegram.models import TelegramPost
from ..x.models import XPost
from .active_trigger import ActiveNarrativeTrigger, investigate_active_trigger
from .catalyst_mint import CatalystMintMatch
from .catalyst_mint_trigger import passive_trigger_from_catalyst_mint
from .market_signal import MarketAnomaly
from .market_trigger import passive_trigger_from_market
from .passive_trigger import investigate_passive_signal, investigate_passive_trigger
from .research_package import (
    NarrativeResearchPackage,
    package_active_failure,
    package_active_result,
    package_passive_result,
    package_telegram_result,
    ResearchMode,
)
from .research_store import NarrativeResearchStore
from .trusted_ingest import XStatusVerifier
from .trusted_telegram import TelegramPostVerifier
from .telegram_trigger import (
    TelegramNarrativeTrigger,
    investigate_telegram_trigger,
)


class ActivePostMonitor(Protocol):
    def monitor_once(self) -> tuple[XPost, ...]: ...


class GrokResearchClient(Protocol):
    def search(self, prompt: str, *, instructions: str): ...


class NarrativeResearchRuntime:
    """Persist research from key-person posts and DeBot signals, never trades."""

    def __init__(
        self,
        *,
        monitor: ActivePostMonitor,
        grok: GrokResearchClient,
        verifier: XStatusVerifier,
        telegram_verifier: TelegramPostVerifier | None = None,
        store: NarrativeResearchStore,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self.monitor = monitor
        self.grok = grok
        self.verifier = verifier
        self.telegram_verifier = telegram_verifier
        self.store = store
        self.clock = clock

    def poll_active(self) -> tuple[NarrativeResearchPackage, ...]:
        """Research every newly monitored key-person post independently."""

        packages: list[NarrativeResearchPackage] = []
        for post in self.monitor.monitor_once():
            trigger = ActiveNarrativeTrigger.from_post(post)
            try:
                package = self.research_active_post(post)
            except Exception as exc:
                package = package_active_failure(
                    trigger, self.clock(), type(exc).__name__
                )
                self.store.append(package)
            packages.append(package)
        return tuple(packages)

    def research_active_post(self, post: XPost) -> NarrativeResearchPackage:
        """Research one immutable actor post; let failures reach queue retry."""

        trigger = ActiveNarrativeTrigger.from_post(post)
        result = investigate_active_trigger(
            trigger, grok=self.grok, verifier=self.verifier
        )
        package = package_active_result(result, self.clock())
        self.store.append(package)
        return package

    def research_debot_signal(
        self, signal: DeBotSignal, *, anomaly: str | None = None
    ) -> NarrativeResearchPackage:
        """Run market-first narrative search for one immutable DeBot signal."""

        result = investigate_passive_signal(
            signal, self.grok, self.verifier, anomaly=anomaly
        )
        package = package_passive_result(result, self.clock())
        self.store.append(package)
        return package

    def research_market_anomaly(
        self, anomaly: MarketAnomaly
    ) -> NarrativeResearchPackage:
        """Investigate why an exact-CA BSC mover is rising right now."""

        result = investigate_passive_trigger(
            passive_trigger_from_market(anomaly), self.grok, self.verifier
        )
        package = package_passive_result(
            result, self.clock(), mode=ResearchMode.PASSIVE_MARKET
        )
        self.store.append(package)
        return package

    def research_catalyst_mint(
        self, match: CatalystMintMatch
    ) -> NarrativeResearchPackage:
        """Investigate one exact no-CA catalyst joined to a subsequent mint."""

        result = investigate_passive_trigger(
            passive_trigger_from_catalyst_mint(match), self.grok, self.verifier
        )
        package = package_passive_result(
            result, self.clock(), mode=ResearchMode.PASSIVE_CATALYST_MINT
        )
        self.store.append(package)
        return package

    def research_telegram_post(
        self, post: TelegramPost
    ) -> NarrativeResearchPackage:
        """Research one exact public Telegram message through the same gate."""

        if self.telegram_verifier is None:
            raise RuntimeError("Telegram verifier is not configured")
        result = investigate_telegram_trigger(
            TelegramNarrativeTrigger.from_post(post),
            grok=self.grok,
            telegram_verifier=self.telegram_verifier,
            x_verifier=self.verifier,
        )
        package = package_telegram_result(result, self.clock())
        self.store.append(package)
        return package

    def run_once(
        self, signals: Iterable[DeBotSignal] = ()
    ) -> tuple[NarrativeResearchPackage, ...]:
        """Research queued DeBot signals first, then poll proactive actors once."""

        passive = tuple(self.research_debot_signal(signal) for signal in signals)
        return passive + self.poll_active()
