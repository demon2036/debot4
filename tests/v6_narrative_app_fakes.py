from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from debot4.v6.narrative import app as narrative_app
from debot4.v6.narrative.service import CollectionCycle, WorkCycle


def patch_app_graph(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, object],
) -> None:
    """Replace external app edges while preserving the assembly contract."""
    closed: list[str] = []
    calls["closed"] = closed

    class Feed:
        @classmethod
        def from_credentials(cls, *args: object, **kwargs: object):
            calls["feed"] = (args, kwargs)
            return cls()

        def close(self) -> None:
            closed.append("feed")

    class Queue:
        def __init__(self, path: Path) -> None:
            calls["queue_path"] = path

        def close(self) -> None:
            closed.append("queue")

    class MintMonitor:
        @classmethod
        def from_credentials(cls, **kwargs: object):
            calls["mint_monitor"] = kwargs
            return cls()

        def close(self) -> None:
            closed.append("mint-monitor")

    class CatalystState:
        def __init__(self, path: Path) -> None:
            calls["catalyst_state_path"] = path

    class AlertGate:
        def __init__(self, path: Path) -> None:
            calls["mint_alert_gate_path"] = path

    class MintLocations:
        def __init__(self, path: Path) -> None:
            calls["mint_location_path"] = path

        def close(self) -> None:
            closed.append("mint-locations")

    class MintAlerts:
        def __init__(self, path: Path) -> None:
            calls["mint_alert_path"] = path

        def close(self) -> None:
            closed.append("mint-alerts")

    class AlertDispatcher:
        def __init__(self, store: object, sink: object) -> None:
            calls["mint_alert_dispatcher"] = (store, sink)
            self.dispatches = 0

        def dispatch_once(self) -> None:
            self.dispatches += 1

        def snapshot(self) -> dict[str, int]:
            return {"delivered": self.dispatches}

    class Rpc:
        def __init__(self, endpoints: tuple[str, ...], **kwargs: object) -> None:
            calls["bsc_rpc"] = (endpoints, kwargs)

        def close(self) -> None:
            closed.append("bsc-rpc")

    class ChainMonitor:
        def __init__(self, **kwargs: object) -> None:
            calls["chain_monitor"] = kwargs
            self.poll_seconds = kwargs["poll_seconds"]

    class Store:
        def __init__(self, path: Path) -> None:
            calls["store_path"] = path

        def close(self) -> None:
            closed.append("store")

    class Collector:
        def __init__(
            self,
            monitor: object,
            telegram: object,
            feed: object,
            queue: object,
            *,
            market_monitor: object | None = None,
            mint_monitor: object | None = None,
            catalyst_mints: object | None = None,
            mint_alert_gate: object | None = None,
            chain_mint_monitor: object | None = None,
            mint_locations: object | None = None,
            mint_alerts: object | None = None,
            signal_filter: object | None = None,
        ) -> None:
            calls.setdefault("collectors", []).append(
                (
                    monitor, telegram, feed, queue, market_monitor,
                    mint_monitor, catalyst_mints, chain_mint_monitor,
                    mint_locations, mint_alerts, signal_filter, mint_alert_gate,
                )
            )
            self.signal_filter = signal_filter

        def collect_once(self) -> CollectionCycle:
            return CollectionCycle(2, 1, 3, 4)

    class Worker:
        def work_once(self) -> WorkCycle:
            return WorkCycle(None, None)

    class Service:
        def __init__(self, **kwargs: object) -> None:
            calls["service"] = kwargs
            self.collector = Collector(
                kwargs["monitor"],
                kwargs["telegram_monitor"],
                kwargs["debot_feed"],
                kwargs["queue"],
                market_monitor=kwargs["market_monitor"],
                mint_monitor=kwargs["mint_monitor"],
                catalyst_mints=kwargs["catalyst_mints"],
                mint_alert_gate=kwargs["mint_alert_gate"],
                chain_mint_monitor=kwargs["chain_mint_monitor"],
                mint_locations=kwargs["mint_locations"],
                mint_alerts=kwargs["mint_alerts"],
                signal_filter=kwargs["signal_filter"],
            )
            self.worker = Worker()
            self.workers = (self.worker,) * kwargs["config"].research_workers

        def run(self, stop: object) -> None:
            calls["run_stop"] = stop

    class Grok:
        @classmethod
        def from_env(cls):
            calls["grok_from_env"] = True
            return cls()

    def make_monitor(
        path: Path, *, client: object, max_workers: int
    ) -> object:
        calls["monitor"] = (path, client, max_workers)
        return SimpleNamespace(name="monitor")

    def make_telegram_monitor(path: Path, *, client: object) -> object:
        calls["telegram_monitor"] = (path, client)
        return SimpleNamespace(name="telegram-monitor")

    def make_runtime(**kwargs: object) -> object:
        calls["runtime"] = kwargs
        return SimpleNamespace(name="runtime")

    def make_mint_sources(settings: object, resources: object) -> object:
        monitor = MintMonitor.from_credentials(
            credential_file=settings.debot_cookie_file,
            timeout_seconds=settings.debot_timeout_seconds,
            max_response_bytes=settings.max_response_bytes,
            poll_seconds=settings.mint_poll_seconds,
        )
        resources.callback(monitor.close)
        locations = MintLocations(settings.mint_location_database)
        resources.callback(locations.close)
        rpc = None
        chain = None
        if settings.chain_mint_audit_enabled:
            rpc = Rpc(
                settings.bsc_rpc_endpoints,
                timeout_seconds=settings.chain_mint_timeout_seconds,
                max_response_bytes=settings.max_response_bytes,
            )
            resources.callback(rpc.close)
            chain = ChainMonitor(
                checkpoint_path=settings.chain_mint_checkpoint_path,
                poll_seconds=settings.chain_mint_poll_seconds,
                startup_lookback_blocks=settings.chain_mint_startup_lookback_blocks,
                max_catchup_blocks=settings.chain_mint_max_catchup_blocks,
            )
        return SimpleNamespace(
            debot=monitor,
            catalyst=CatalystState(settings.catalyst_mint_state_path),
            gate=AlertGate(settings.mint_alert_gate_path),
            locations=locations,
            rpc=rpc,
            chain=chain,
        )

    monkeypatch.setattr(
        narrative_app, "FxJsonHttp", lambda **kwargs: ("fx-http", kwargs)
    )
    monkeypatch.setattr(
        narrative_app, "XTimelineClient", lambda **kwargs: ("timeline", kwargs)
    )
    monkeypatch.setattr(narrative_app, "NarrativeMonitor", make_monitor)
    monkeypatch.setattr(
        narrative_app,
        "TelegramHtmlHttp",
        lambda **kwargs: ("telegram-http", kwargs),
    )
    monkeypatch.setattr(
        narrative_app,
        "TelegramPublicClient",
        lambda **kwargs: ("telegram-client", kwargs),
    )
    monkeypatch.setattr(
        narrative_app, "TelegramNarrativeMonitor", make_telegram_monitor
    )
    monkeypatch.setattr(narrative_app, "NarrativeDeBotFeed", Feed)
    monkeypatch.setattr(narrative_app, "build_mint_sources", make_mint_sources)
    monkeypatch.setattr(narrative_app, "MintAlertStore", MintAlerts)
    monkeypatch.setattr(
        narrative_app, "JsonLineMintAlertSink", lambda: "mint-alert-sink"
    )
    monkeypatch.setattr(narrative_app, "MintAlertDispatcher", AlertDispatcher)
    monkeypatch.setattr(
        narrative_app, "DirectJsonClient", lambda **kwargs: ("market-http", kwargs)
    )
    monkeypatch.setattr(
        narrative_app,
        "MarketAnomalyMonitor",
        lambda *args, **kwargs: ("market-monitor", args, kwargs),
    )
    monkeypatch.setattr(narrative_app, "NarrativeJobQueue", Queue)
    monkeypatch.setattr(narrative_app, "NarrativeResearchStore", Store)
    monkeypatch.setattr(narrative_app, "NarrativeCollector", Collector)
    monkeypatch.setattr(narrative_app, "Grok2ApiClient", Grok)
    monkeypatch.setattr(
        narrative_app,
        "FxTwitterClient",
        lambda **kwargs: ("fx-client", kwargs),
    )
    monkeypatch.setattr(
        narrative_app,
        "XStatusVerifier",
        lambda **kwargs: ("verifier", kwargs),
    )
    monkeypatch.setattr(
        narrative_app,
        "TelegramPostVerifier",
        lambda **kwargs: ("telegram-verifier", kwargs),
    )
    monkeypatch.setattr(narrative_app, "NarrativeResearchRuntime", make_runtime)
    monkeypatch.setattr(narrative_app, "NarrativeService", Service)
    monkeypatch.setattr(
        narrative_app,
        "load_telegram_realtime_config",
        lambda path: ("private-config", path),
    )
    monkeypatch.setattr(
        narrative_app,
        "TelegramRealtimeMonitor",
        lambda config, channels, **kwargs: (
            "telegram-realtime",
            config,
            channels,
            kwargs,
        ),
    )
