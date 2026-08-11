from pathlib import Path

import pytest

from debot4.v6.narrative.settings import NarrativeSettings


def test_defaults_are_fast_and_use_isolated_state_directory() -> None:
    settings = NarrativeSettings.from_env({})
    assert settings.collector_tick_seconds == 0.25
    assert settings.debot_poll_seconds == 2.0
    assert settings.market_poll_seconds == 5.0
    assert settings.market_checkpoint_path.name == "market-anomalies.json"
    assert settings.queue_database.name == "jobs.sqlite3"
    assert settings.research_database.parent == settings.state_dir


def test_environment_overrides_are_validated(tmp_path: Path) -> None:
    settings = NarrativeSettings.from_env({
        "DEBOT4_NARRATIVE_STATE_DIR": str(tmp_path / "state"),
        "DEBOT4_DEBOT_COOKIE_FILE": str(tmp_path / "debot-cookies.json"),
        "DEBOT4_TELEGRAM_REALTIME_CONFIG": str(tmp_path / "telegram.json"),
        "DEBOT4_COLLECTOR_TICK_SECONDS": "0.1",
        "DEBOT4_DEBOT_POLL_SECONDS": "0.5",
        "DEBOT4_MARKET_POLL_SECONDS": "1.5",
        "DEBOT4_MARKET_TIMEOUT_SECONDS": "3",
        "DEBOT4_JOB_LEASE_SECONDS": "300",
        "DEBOT4_TELEGRAM_REALTIME_RETRY_SECONDS": "0.5",
        "DEBOT4_MAX_RESPONSE_BYTES": "4096",
    })
    assert settings.state_dir == (tmp_path / "state").resolve()
    assert settings.debot_cookie_file == (tmp_path / "debot-cookies.json").resolve()
    assert settings.telegram_realtime_config == (tmp_path / "telegram.json").resolve()
    assert settings.collector_tick_seconds == 0.1
    assert settings.debot_poll_seconds == 0.5
    assert settings.market_poll_seconds == 1.5
    assert settings.market_timeout_seconds == 3
    assert settings.lease_seconds == 300
    assert settings.telegram_realtime_retry_seconds == 0.5
    assert settings.max_response_bytes == 4096


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("DEBOT4_COLLECTOR_TICK_SECONDS", "3"),
        ("DEBOT4_DEBOT_POLL_SECONDS", "30"),
        ("DEBOT4_MARKET_POLL_SECONDS", "30"),
        ("DEBOT4_JOB_LEASE_SECONDS", "2"),
        ("DEBOT4_MAX_RESPONSE_BYTES", "1.5"),
    ],
)
def test_invalid_runtime_values_fail_closed(key: str, value: str) -> None:
    with pytest.raises(ValueError):
        NarrativeSettings.from_env({key: value})
