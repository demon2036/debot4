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
        ) -> None:
            calls.setdefault("collectors", []).append(
                (monitor, telegram, feed, queue, market_monitor)
            )

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
            )
            self.worker = Worker()

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
