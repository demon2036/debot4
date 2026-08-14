"""Production assembly for the independent v6 narrative runtime."""

from __future__ import annotations

from contextlib import ExitStack

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
    XTimelineClient,
)
from .debot_feed import NarrativeDeBotFeed
from .actor_registry import DEFAULT_ACTOR_REGISTRY
from .app_runtime import NarrativeApp
from .app_x_sources import x_egress as _x_egress, x_reposts as _x_reposts
from .app_mint_sources import build_mint_sources
from .fxtwitter import FxTwitterClient
from .job_queue import NarrativeJobQueue
from .live_signal_filter import BscRealtimeSignalFilter
from .market_monitor import MarketAnomalyMonitor
from .research_runtime import NarrativeResearchRuntime
from .research_store import NarrativeResearchStore
from .service import (
    NarrativeCollector,
    NarrativeService,
    NarrativeServiceConfig,
)
from .settings import NarrativeSettings
from .monitor import NarrativeMonitor
from .telegram_monitor import TelegramNarrativeMonitor
from .trusted_ingest import XStatusVerifier
from .trusted_telegram import TelegramPostVerifier


def build_narrative_app(
    settings: NarrativeSettings | None = None,
    *,
    research: bool = True,
) -> NarrativeApp:
    """Build a collector-only or full research application from local settings."""

    config = settings or NarrativeSettings.from_env()
    resources = ExitStack()
    try:
        x_egress_pool = _x_egress(config)
        if x_egress_pool is not None:
            resources.callback(x_egress_pool.close)
        x_http = FxJsonHttp(
            timeout_seconds=config.x_timeout_seconds,
            max_response_bytes=config.max_response_bytes,
            opener=x_egress_pool,
        )
        x_client = XTimelineClient(http=x_http)
        monitor = NarrativeMonitor(
            config.x_checkpoint_path,
            client=x_client,
            max_workers=config.x_monitor_workers,
        )
        x_repost_monitor = _x_reposts(config, x_http)
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
        mint_sources = build_mint_sources(config, resources)
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
        signal_filter = BscRealtimeSignalFilter(DEFAULT_ACTOR_REGISTRY)
        collector = NarrativeCollector(
            monitor,
            telegram_monitor,
            debot_feed,
            queue,
            market_monitor=market_monitor,
            mint_monitor=mint_sources.debot,
            catalyst_mints=mint_sources.catalyst,
            chain_mint_monitor=mint_sources.chain,
            mint_locations=mint_sources.locations,
            signal_filter=signal_filter,
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
            mint_monitor=mint_sources.debot,
            catalyst_mints=mint_sources.catalyst,
            chain_mint_monitor=mint_sources.chain,
            mint_locations=mint_sources.locations,
            bsc_mint_rpc=mint_sources.rpc,
            queue=queue,
            collector=collector,
            x_egress_pool=x_egress_pool,
            _resources=resources,
        )
        if not research:
            return app

        realtime = _telegram_realtime(config)
        grok = Grok2ApiClient.from_env()
        verifier = XStatusVerifier(fetcher=FxTwitterClient(
            timeout_seconds=config.x_timeout_seconds,
            max_response_bytes=config.max_response_bytes,
            opener=x_egress_pool,
        ))
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
            mint_monitor=mint_sources.debot,
            catalyst_mints=mint_sources.catalyst,
            chain_mint_monitor=mint_sources.chain,
            mint_locations=mint_sources.locations,
            queue=queue,
            research_runtime=runtime,
            telegram_realtime=realtime,
            x_repost_monitor=x_repost_monitor,
            config=NarrativeServiceConfig(
                collector_seconds=config.collector_tick_seconds,
                worker_idle_seconds=config.worker_idle_seconds,
                lease_seconds=config.lease_seconds,
                retry_delay_seconds=config.retry_delay_seconds,
                research_workers=config.research_workers,
            ),
            signal_filter=signal_filter,
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
