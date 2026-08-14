from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from debot4.v6.narrative import app as narrative_app
from debot4.v6.narrative.service import CollectionCycle, WorkCycle
from debot4.v6.narrative.settings import NarrativeSettings
from tests.v6_narrative_app_fakes import patch_app_graph


def _settings(tmp_path: Path) -> NarrativeSettings:
    return NarrativeSettings(
        state_dir=tmp_path / "state",
        debot_cookie_file=tmp_path / "debot-cookies.json",
        collector_tick_seconds=0.5,
        debot_poll_seconds=1.5,
        mint_poll_seconds=0.75,
        chain_mint_audit_enabled=True,
        market_poll_seconds=2.5,
        worker_idle_seconds=0.75,
        retry_delay_seconds=4,
        lease_seconds=90,
        debot_timeout_seconds=3,
        market_timeout_seconds=2,
        max_response_bytes=123_456,
    )


def test_full_app_wires_real_interfaces_and_closes_in_reverse_order(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    patch_app_graph(monkeypatch, calls)
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
    monitor_path, timeline, workers = calls["monitor"]
    assert monitor_path == settings.x_checkpoint_path
    assert timeline == ("timeline", {"http": ("fx-http", {
        "timeout_seconds": settings.x_timeout_seconds,
        "max_response_bytes": settings.max_response_bytes,
        "opener": None,
    })})
    assert workers == 40
    assert calls["queue_path"] == settings.queue_database
    assert calls["mint_monitor"] == {
        "credential_file": settings.debot_cookie_file,
        "timeout_seconds": 3,
        "max_response_bytes": 123_456,
        "poll_seconds": 0.75,
    }
    assert calls["catalyst_state_path"] == settings.catalyst_mint_state_path
    assert calls["mint_alert_gate_path"] == settings.mint_alert_gate_path
    assert calls["mint_location_path"] == settings.mint_location_database
    assert calls["mint_alert_path"] == settings.mint_alert_database
    assert calls["mint_alert_dispatcher"] == (
        app.mint_alerts, "mint-alert-sink"
    )
    assert calls["bsc_rpc"] == (settings.bsc_rpc_endpoints, {
        "timeout_seconds": settings.chain_mint_timeout_seconds,
        "max_response_bytes": settings.max_response_bytes,
    })
    assert calls["chain_monitor"] == {
        "checkpoint_path": settings.chain_mint_checkpoint_path,
        "poll_seconds": settings.chain_mint_poll_seconds,
        "startup_lookback_blocks": settings.chain_mint_startup_lookback_blocks,
        "max_catchup_blocks": settings.chain_mint_max_catchup_blocks,
    }
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
    assert calls["runtime"]["verifier"] == ("verifier", {
        "fetcher": ("fx-client", {
            "timeout_seconds": settings.x_timeout_seconds,
            "max_response_bytes": settings.max_response_bytes,
            "opener": None,
        }),
    })
    service = calls["service"]
    assert service["monitor"] is app.monitor
    assert service["telegram_monitor"] is app.telegram_monitor
    assert service["debot_feed"] is app.debot_feed
    assert service["market_monitor"] is app.market_monitor
    assert service["mint_monitor"] is app.mint_monitor
    assert service["catalyst_mints"] is app.catalyst_mints
    assert service["mint_alert_gate"] is app.mint_alert_gate
    assert service["chain_mint_monitor"] is app.chain_mint_monitor
    assert service["mint_locations"] is app.mint_locations
    assert service["mint_alerts"] is app.mint_alerts
    assert service["mint_alert_dispatcher"] is app.mint_alert_dispatcher
    assert service["queue"] is app.queue
    assert service["research_runtime"] is app.research_runtime
    assert service["telegram_realtime"] is None
    assert service["x_repost_monitor"] is app.x_repost_monitor
    assert service["signal_filter"] is app.collector.signal_filter
    config = service["config"]
    assert config.collector_seconds == 0.5
    assert config.worker_idle_seconds == 0.75
    assert config.lease_seconds == 90
    assert config.retry_delay_seconds == 4
    assert config.research_workers == 10

    app.close()
    app.close()
    assert calls["closed"] == [
        "store", "queue", "mint-alerts", "bsc-rpc", "mint-locations",
        "mint-monitor", "feed",
    ]


def test_collection_app_never_loads_grok_and_rejects_worker_use(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    patch_app_graph(monkeypatch, calls)

    with narrative_app.build_collection_app(_settings(tmp_path)) as app:
        assert app.collect_once() == CollectionCycle(2, 1, 3, 4)
        assert app.mint_alert_dispatcher.dispatches == 1
        assert app.grok is None and app.research_store is None
        with pytest.raises(RuntimeError, match="not configured"):
            app.work_once()

    assert "grok_from_env" not in calls
    assert "store_path" not in calls
    assert calls["closed"] == [
        "queue", "mint-alerts", "bsc-rpc", "mint-locations",
        "mint-monitor", "feed",
    ]


def test_chain_rpc_audit_is_not_built_when_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    patch_app_graph(monkeypatch, calls)
    settings = replace(_settings(tmp_path), chain_mint_audit_enabled=False)

    with narrative_app.build_collection_app(settings) as app:
        assert app.bsc_mint_rpc is None
        assert app.chain_mint_monitor is None
        assert calls["collectors"][-1][7] is None

    assert "bsc_rpc" not in calls and "chain_monitor" not in calls
    assert calls["closed"] == [
        "queue", "mint-alerts", "mint-locations", "mint-monitor", "feed",
    ]


def test_full_app_wires_private_realtime_config_only_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}
    patch_app_graph(monkeypatch, calls)
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
    patch_app_graph(monkeypatch, calls)

    class BrokenGrok:
        @classmethod
        def from_env(cls):
            raise RuntimeError("private key contents must never escape")

    monkeypatch.setattr(narrative_app, "Grok2ApiClient", BrokenGrok)

    with pytest.raises(RuntimeError, match="private key"):
        narrative_app.build_narrative_app(_settings(tmp_path))

    assert calls["closed"] == [
        "queue", "mint-alerts", "bsc-rpc", "mint-locations",
        "mint-monitor", "feed",
    ]
