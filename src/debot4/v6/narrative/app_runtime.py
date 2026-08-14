"""Owned runtime graph and lifecycle for the narrative application."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from threading import Event

from ..grok import Grok2ApiClient
from ..telegram import TelegramPublicClient, TelegramRealtimeMonitor
from ..x import FxEgressPool, FxTwitterRepostMonitor
from .bsc_mint_rpc import BscMintRpcClient
from .catalyst_mint_state import CatalystMintState
from .chain_mint_monitor import BscMintMonitor
from .debot_feed import NarrativeDeBotFeed
from .job_queue import NarrativeJobQueue
from .market_monitor import MarketAnomalyMonitor
from .mint_alert_delivery import MintAlertDispatcher
from .mint_alert_store import MintAlertStore
from .mint_location_store import MintLocationStore
from .mint_monitor import NarrativeMintMonitor
from .monitor import NarrativeMonitor
from .research_runtime import NarrativeResearchRuntime
from .research_store import NarrativeResearchStore
from .service import CollectionCycle, NarrativeCollector, NarrativeService, WorkCycle
from .settings import NarrativeSettings
from .telegram_monitor import TelegramNarrativeMonitor
from .trusted_ingest import XStatusVerifier
from .trusted_telegram import TelegramPostVerifier


@dataclass(slots=True)
class NarrativeApp:
    """Owned runtime graph with deterministic, idempotent cleanup."""

    settings: NarrativeSettings
    monitor: NarrativeMonitor
    telegram_monitor: TelegramNarrativeMonitor
    telegram_client: TelegramPublicClient
    telegram_realtime: TelegramRealtimeMonitor | None
    x_repost_monitor: FxTwitterRepostMonitor | None
    debot_feed: NarrativeDeBotFeed
    market_monitor: MarketAnomalyMonitor
    mint_monitor: NarrativeMintMonitor
    catalyst_mints: CatalystMintState
    chain_mint_monitor: BscMintMonitor | None
    mint_locations: MintLocationStore
    mint_alerts: MintAlertStore
    mint_alert_dispatcher: MintAlertDispatcher
    bsc_mint_rpc: BscMintRpcClient | None
    queue: NarrativeJobQueue
    collector: NarrativeCollector
    x_egress_pool: FxEgressPool | None = None
    grok: Grok2ApiClient | None = None
    verifier: XStatusVerifier | None = None
    telegram_verifier: TelegramPostVerifier | None = None
    research_store: NarrativeResearchStore | None = None
    research_runtime: NarrativeResearchRuntime | None = None
    service: NarrativeService | None = None
    _resources: ExitStack = field(default_factory=ExitStack, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def __enter__(self) -> "NarrativeApp":
        self._ensure_open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._resources.close()

    def collect_once(self) -> CollectionCycle:
        self._ensure_open()
        cycle = self.collector.collect_once()
        self.mint_alert_dispatcher.dispatch_once()
        return cycle

    def work_once(self) -> WorkCycle:
        self._ensure_open()
        if self.service is None:
            raise RuntimeError("narrative research is not configured")
        return self.service.worker.work_once()

    def run(self, stop: Event) -> None:
        self._ensure_open()
        if self.service is None:
            raise RuntimeError("narrative research is not configured")
        self.service.run(stop)

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError("narrative application is closed")
