from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace

import pytest

from debot4.v6.narrative import app as narrative_app
from debot4.v6.narrative.service import CollectionCycle, WorkCycle
from debot4.v6.narrative.settings import NarrativeSettings


def _settings(tmp_path: Path) -> NarrativeSettings:
    return NarrativeSettings(
        state_dir=tmp_path / "state",
        debot_cookie_file=tmp_path / "debot-cookies.json",
        collector_tick_seconds=0.5,
        debot_poll_seconds=1.5,
        market_poll_seconds=2.5,
        worker_idle_seconds=0.75,
        retry_delay_seconds=4,
        lease_seconds=90,
        debot_timeout_seconds=3,
        market_timeout_seconds=2,
        max_response_bytes=123_456,
    )


def _patch_graph(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, object],
) -> None:
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
            self, monitor: object, telegram: object, feed: object, queue: object,
            *, market_monitor: object | None = None,
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
                kwargs["monitor"], kwargs["telegram_monitor"],
                kwargs["debot_feed"], kwargs["queue"],
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

    def make_monitor(path: Path, *, client: object) -> object:
        calls["monitor"] = (path, client)
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
    monkeypatch.setattr(narrative_app, "FxTwitterClient", lambda: "fx-client")
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
            "telegram-realtime", config, channels, kwargs
        ),
    )


def test_full_app_wires_real_interfaces_and_closes_in_reverse_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    _patch_graph(monkeypatch, calls)
    settings = _settings(tmp_path)

    app = narrative_app.build_narrative_app(settings)

    feed_args, feed_kwargs = calls["feed"]
    assert feed_args == (settings.debot_checkpoint_path,)
    assert feed_kwargs == {
        "credential_file": settings.debot_cookie_file,
        "timeout_seconds": 3,
        "max_response_bytes": 123_456,
        "poll_seconds": 1.5,
    }
    monitor_path, timeline = calls["monitor"]
    assert monitor_path == settings.x_checkpoint_path
    assert timeline == ("timeline", {"http": ("fx-http", {
        "timeout_seconds": settings.x_timeout_seconds,
        "max_response_bytes": settings.max_response_bytes,
    })})
    assert calls["queue_path"] == settings.queue_database
    market = app.market_monitor
    assert market[1] == (settings.market_checkpoint_path,)
    assert market[2]["poll_seconds"] == 2.5
    assert market[2]["client"] == ("market-http", {
        "timeout_seconds": 2, "max_response_bytes": 123_456,
    })
    telegram_path, telegram_client = calls["telegram_monitor"]
    assert telegram_path == settings.telegram_checkpoint_path
    assert telegram_client == ("telegram-client", {"http": (
        "telegram-http", {
            "timeout_seconds": settings.telegram_timeout_seconds,
            "max_response_bytes": settings.max_response_bytes,
        }
    )})
    assert calls["store_path"] == settings.research_database
    assert calls["grok_from_env"] is True
    assert calls["runtime"] == {
        "monitor": app.monitor,
        "grok": app.grok,
        "verifier": app.verifier,
        "telegram_verifier": app.telegram_verifier,
        "store": app.research_store,
    }
    service = calls["service"]
    assert service["monitor"] is app.monitor
    assert service["telegram_monitor"] is app.telegram_monitor
    assert service["debot_feed"] is app.debot_feed
    assert service["market_monitor"] is app.market_monitor
    assert service["queue"] is app.queue
    assert service["research_runtime"] is app.research_runtime
    assert service["telegram_realtime"] is None
    assert service["x_repost_monitor"] is app.x_repost_monitor
    config = service["config"]
    assert config.collector_seconds == 0.5
    assert config.worker_idle_seconds == 0.75
    assert config.lease_seconds == 90
    assert config.retry_delay_seconds == 4

    app.close()
    app.close()
    assert calls["closed"] == ["store", "queue", "feed"]


def test_collection_app_never_loads_grok_and_rejects_worker_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    _patch_graph(monkeypatch, calls)

    with narrative_app.build_collection_app(_settings(tmp_path)) as app:
        assert app.collect_once() == CollectionCycle(2, 1, 3, 4)
        assert app.grok is None and app.research_store is None
        with pytest.raises(RuntimeError, match="not configured"):
            app.work_once()

    assert "grok_from_env" not in calls
    assert "store_path" not in calls
    assert calls["closed"] == ["queue", "feed"]


def test_full_app_wires_private_realtime_config_only_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    _patch_graph(monkeypatch, calls)
    private_path = tmp_path / "telegram.json"
    settings = replace(
        _settings(tmp_path), telegram_realtime_config=private_path,
        telegram_realtime_retry_seconds=0.75,
    )

    with narrative_app.build_narrative_app(settings) as app:
        realtime = app.telegram_realtime
        assert realtime[0] == "telegram-realtime"
        assert realtime[1] == ("private-config", private_path.resolve())
        assert realtime[3] == {"retry_seconds": 0.75}
        assert calls["service"]["telegram_realtime"] is realtime


def test_failed_research_assembly_closes_collector_resources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    _patch_graph(monkeypatch, calls)

    class BrokenGrok:
        @classmethod
        def from_env(cls):
            raise RuntimeError("private key contents must never escape")

    monkeypatch.setattr(narrative_app, "Grok2ApiClient", BrokenGrok)

    with pytest.raises(RuntimeError, match="private key"):
        narrative_app.build_narrative_app(_settings(tmp_path))

    assert calls["closed"] == ["queue", "feed"]
