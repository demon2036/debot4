"""Production assembly for the independent v6 narrative runtime."""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass, field
from threading import Event

from ..grok import Grok2ApiClient
from ..dex_audit.http import DirectJsonClient
from ..telegram import (
    TelegramPublicClient,
    TelegramRealtimeMonitor,
    load_telegram_realtime_config,
)
from ..telegram.http import TelegramHtmlHttp
from ..x import (
    FxJsonHttp,
    FxTwitterRepostMonitor,
    XRepostTarget,
    XTimelineClient,
)
from .debot_feed import NarrativeDeBotFeed
from .actor_registry import DEFAULT_ACTOR_REGISTRY
from .fxtwitter import FxTwitterClient
from .job_queue import NarrativeJobQueue
from .market_monitor import MarketAnomalyMonitor
from .research_runtime import NarrativeResearchRuntime
from .research_store import NarrativeResearchStore
from .service import (
    CollectionCycle,
    NarrativeCollector,
    NarrativeService,
    NarrativeServiceConfig,
    WorkCycle,
)
from .settings import NarrativeSettings
from .monitor import NarrativeMonitor
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
    queue: NarrativeJobQueue
    collector: NarrativeCollector
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
        return self.collector.collect_once()

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


def build_narrative_app(
    settings: NarrativeSettings | None = None,
    *,
    research: bool = True,
) -> NarrativeApp:
    """Build a collector-only or full research application from local settings."""

    config = settings or NarrativeSettings.from_env()
    resources = ExitStack()
    try:
        x_client = XTimelineClient(http=FxJsonHttp(
            timeout_seconds=config.x_timeout_seconds,
            max_response_bytes=config.max_response_bytes,
        ))
        monitor = NarrativeMonitor(config.x_checkpoint_path, client=x_client)
        x_repost_monitor = _x_reposts(config)
        telegram_client = TelegramPublicClient(http=TelegramHtmlHttp(
            timeout_seconds=config.telegram_timeout_seconds,
            max_response_bytes=config.max_response_bytes,
        ))
        telegram_monitor = TelegramNarrativeMonitor(
            config.telegram_checkpoint_path, client=telegram_client
        )
        debot_feed = NarrativeDeBotFeed.from_credentials(
            config.debot_checkpoint_path,
            credential_file=config.debot_cookie_file,
            timeout_seconds=config.debot_timeout_seconds,
            max_response_bytes=config.max_response_bytes,
            poll_seconds=config.debot_poll_seconds,
        )
        resources.callback(debot_feed.close)
        market_monitor = MarketAnomalyMonitor(
            config.market_checkpoint_path,
            client=DirectJsonClient(
                timeout_seconds=config.market_timeout_seconds,
                max_response_bytes=config.max_response_bytes,
            ),
            poll_seconds=config.market_poll_seconds,
        )
        queue = NarrativeJobQueue(config.queue_database)
        resources.callback(queue.close)
        collector = NarrativeCollector(
            monitor,
            telegram_monitor,
            debot_feed,
            queue,
            market_monitor=market_monitor,
        )
        app = NarrativeApp(
            settings=config,
            monitor=monitor,
            telegram_monitor=telegram_monitor,
            telegram_client=telegram_client,
            telegram_realtime=None,
            x_repost_monitor=x_repost_monitor,
            debot_feed=debot_feed,
            market_monitor=market_monitor,
            queue=queue,
            collector=collector,
            _resources=resources,
        )
        if not research:
            return app

        realtime = _telegram_realtime(config)
        grok = Grok2ApiClient.from_env()
        verifier = XStatusVerifier(fetcher=FxTwitterClient())
        telegram_verifier = TelegramPostVerifier(fetcher=telegram_client)
        store = NarrativeResearchStore(config.research_database)
        resources.callback(store.close)
        runtime = NarrativeResearchRuntime(
            monitor=monitor,
            grok=grok,
            verifier=verifier,
            telegram_verifier=telegram_verifier,
            store=store,
        )
        service = NarrativeService(
            monitor=monitor,
            telegram_monitor=telegram_monitor,
            debot_feed=debot_feed,
            market_monitor=market_monitor,
            queue=queue,
            research_runtime=runtime,
            telegram_realtime=realtime,
            x_repost_monitor=x_repost_monitor,
            config=NarrativeServiceConfig(
                collector_seconds=config.collector_tick_seconds,
                worker_idle_seconds=config.worker_idle_seconds,
                lease_seconds=config.lease_seconds,
                retry_delay_seconds=config.retry_delay_seconds,
            ),
        )
        app.collector = service.collector
        app.telegram_realtime = realtime
        app.grok = grok
        app.verifier = verifier
        app.telegram_verifier = telegram_verifier
        app.research_store = store
        app.research_runtime = runtime
        app.service = service
        return app
    except BaseException:
        try:
            resources.close()
        except BaseException:
            pass
        raise


def build_collection_app(
    settings: NarrativeSettings | None = None,
) -> NarrativeApp:
    """Build the credential-independent fast collection path."""

    return build_narrative_app(settings, research=False)


def _telegram_realtime(
    settings: NarrativeSettings,
) -> TelegramRealtimeMonitor | None:
    path = settings.telegram_realtime_config
    if path is None:
        return None
    channels = tuple(dict.fromkeys(
        channel
        for registration in DEFAULT_ACTOR_REGISTRY.registrations()
        for channel in registration.actor.telegram_realtime_channels
    ))
    return TelegramRealtimeMonitor(
        load_telegram_realtime_config(path),
        channels,
        retry_seconds=settings.telegram_realtime_retry_seconds,
    )


def _x_reposts(settings: NarrativeSettings) -> FxTwitterRepostMonitor | None:
    targets = tuple(
        XRepostTarget(actor.handle, registration.author_ids[0])
        for registration in DEFAULT_ACTOR_REGISTRY.registrations()
        if registration.author_ids
        for actor in (registration.actor,)
        if actor.monitor_reposts
    )
    if not targets:
        return None
    return FxTwitterRepostMonitor(
        targets,
        http=FxJsonHttp(
            timeout_seconds=settings.x_timeout_seconds,
            max_response_bytes=settings.max_response_bytes,
        ),
    )
