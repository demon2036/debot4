from pathlib import Path

import pytest

from debot4.v6.narrative.settings import NarrativeSettings


def test_defaults_are_fast_and_use_isolated_state_directory() -> None:
    settings = NarrativeSettings.from_env({})
    assert settings.collector_tick_seconds == 0.25
    assert settings.debot_poll_seconds == 2.0
    assert settings.mint_poll_seconds == 1.0
    assert settings.market_poll_seconds == 5.0
    assert settings.x_egress_pool_file.name == "egress-pool.toml"
    assert settings.x_egress_location == "local"
    assert settings.x_egress_attempts == 3
    assert settings.x_monitor_workers == 40
    assert settings.x_repost_workers == 10
    assert settings.research_workers == 10
    assert settings.market_checkpoint_path.name == "market-anomalies.json"
    assert settings.catalyst_mint_state_path.name == "catalyst-mints.json"
    assert settings.queue_database.name == "jobs.sqlite3"
    assert settings.research_database.parent == settings.state_dir


def test_environment_overrides_are_validated(tmp_path: Path) -> None:
    settings = NarrativeSettings.from_env({
        "DEBOT4_NARRATIVE_STATE_DIR": str(tmp_path / "state"),
        "DEBOT4_DEBOT_COOKIE_FILE": str(tmp_path / "debot-cookies.json"),
        "DEBOT4_TELEGRAM_REALTIME_CONFIG": str(tmp_path / "telegram.json"),
        "DEBOT4_COLLECTOR_TICK_SECONDS": "0.1",
        "DEBOT4_DEBOT_POLL_SECONDS": "0.5",
        "DEBOT4_MINT_POLL_SECONDS": "0.75",
        "DEBOT4_MARKET_POLL_SECONDS": "1.5",
        "DEBOT4_MARKET_TIMEOUT_SECONDS": "3",
        "DEBOT4_X_EGRESS_POOL_FILE": str(tmp_path / "egress.toml"),
        "DEBOT4_X_EGRESS_LOCATION": "remote",
        "DEBOT4_X_EGRESS_ATTEMPTS": "5",
        "DEBOT4_X_MONITOR_WORKERS": "48",
        "DEBOT4_X_REPOST_WORKERS": "8",
        "DEBOT4_RESEARCH_WORKERS": "6",
        "DEBOT4_JOB_LEASE_SECONDS": "300",
        "DEBOT4_TELEGRAM_REALTIME_RETRY_SECONDS": "0.5",
        "DEBOT4_MAX_RESPONSE_BYTES": "4096",
    })
    assert settings.state_dir == (tmp_path / "state").resolve()
    assert settings.debot_cookie_file == (tmp_path / "debot-cookies.json").resolve()
    assert settings.telegram_realtime_config == (tmp_path / "telegram.json").resolve()
    assert settings.collector_tick_seconds == 0.1
    assert settings.debot_poll_seconds == 0.5
    assert settings.mint_poll_seconds == 0.75
    assert settings.market_poll_seconds == 1.5
    assert settings.market_timeout_seconds == 3
    assert settings.x_egress_pool_file == (tmp_path / "egress.toml").resolve()
    assert settings.x_egress_location == "remote"
    assert settings.x_egress_attempts == 5
    assert settings.x_monitor_workers == 48
    assert settings.x_repost_workers == 8
    assert settings.research_workers == 6
    assert settings.lease_seconds == 300
    assert settings.telegram_realtime_retry_seconds == 0.5
    assert settings.max_response_bytes == 4096


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DEBOT4_COLLECTOR_TICK_SECONDS", "3"),
        ("DEBOT4_DEBOT_POLL_SECONDS", "30"),
        ("DEBOT4_MINT_POLL_SECONDS", "0.1"),
        ("DEBOT4_MARKET_POLL_SECONDS", "30"),
        ("DEBOT4_JOB_LEASE_SECONDS", "2"),
        ("DEBOT4_X_EGRESS_ATTEMPTS", "11"),
        ("DEBOT4_X_MONITOR_WORKERS", "0"),
        ("DEBOT4_X_REPOST_WORKERS", "33"),
        ("DEBOT4_RESEARCH_WORKERS", "17"),
        ("DEBOT4_MAX_RESPONSE_BYTES", "1.5"),
    ],
)
def test_invalid_runtime_values_fail_closed(key: str, value: str) -> None:
    with pytest.raises(ValueError):
        NarrativeSettings.from_env({key: value})
