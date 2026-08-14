from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from debot4.v6.debot.credentials import DeBotCookie, save_debot_cookies
from debot4.v6.narrative.job_queue import SCHEMA as JOB_SCHEMA
from debot4.v6.narrative.chain_mint_state import (
    ChainMintCheckpoint,
    ChainMintCheckpointStore,
)
from debot4.v6.narrative.mint_location import DEBOT_NEW_SOURCE, MintLocation
from debot4.v6.narrative.mint_location_store import MintLocationStore
from debot4.v6.narrative.research_store import SCHEMA as RESEARCH_SCHEMA
from debot4.v6.narrative.settings import NarrativeSettings
from debot4.v6.narrative.status import status_snapshot


NOW = datetime(2026, 8, 9, 12, tzinfo=timezone.utc)


def _settings(tmp_path: Path) -> NarrativeSettings:
    return NarrativeSettings(
        tmp_path / "state", tmp_path / "debot-cookies.json",
        collector_tick_seconds=0.25, debot_poll_seconds=1.0,
    )


def _databases(settings: NarrativeSettings) -> None:
    settings.state_dir.mkdir(parents=True)
    stamp = NOW.isoformat()
    with sqlite3.connect(settings.queue_database) as database:
        database.executescript(JOB_SCHEMA)
        base = ["active_x_post", "a" * 64, "{}", 0, 3, stamp, stamp, stamp]
        for number, status in enumerate(("pending", "done", "failed"), 1):
            completed = stamp if status in {"done", "failed"} else None
            database.execute(
                "INSERT INTO narrative_jobs "
                "(job_id,kind,content_sha256,payload_json,status,attempts,max_attempts,"
                "available_at,created_at,updated_at,completed_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [f"job-{number}", *base[:3], status, *base[3:], completed],
            )
    with sqlite3.connect(settings.research_database) as database:
        database.executescript(RESEARCH_SCHEMA)
        for number, minute in ((1, "01"), (2, "02")):
            researched = f"2026-08-09T12:{minute}:00+00:00"
            database.execute(
                "INSERT INTO narrative_research_packages VALUES "
                "(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    f"package-{number}", "schema", "ACTIVE_ACTOR", f"trigger-{number}",
                    stamp, researched, "READY", f"reason-{number}", "b" * 64,
                    0, json.dumps({"secret": f"research-body-{number}"}), stamp,
                ),
            )
    with MintLocationStore(
        settings.mint_location_database, clock=lambda: NOW
    ) as locations:
        locations.record((MintLocation(
            exact_ca="0x417bda357cce720467edc56ebc6bb4c9ea497777",
            source=DEBOT_NEW_SOURCE, observed_at=NOW, created_at=None,
        ),))
    ChainMintCheckpointStore(settings.chain_mint_checkpoint_path).save(
        ChainMintCheckpoint(115_824_174, "0x" + "1" * 64)
    )


def _cookies(settings: NarrativeSettings) -> None:
    save_debot_cookies(settings.debot_cookie_file, (
        DeBotCookie("session", "debot-secret", ".debot.ai", "/"),
    ))


def test_snapshot_reads_exact_databases_and_never_exposes_credentials(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    _databases(settings)
    _cookies(settings)
    env = {
        "DEBOT4_GROK2API_KEY": "grok-secret-value",
        "DEBOT4_X_AUTH_TOKEN": "x-secret-token",
        "DEBOT4_X_CT0": "x-secret-csrf",
    }

    snapshot = status_snapshot(
        settings, environ=env, recent_limit=1, clock=lambda: NOW
    )

    assert snapshot["generated_at"] == NOW.isoformat()
    assert snapshot["research_only"] is True
    assert snapshot["authorizes_trade"] is False
    assert snapshot["profitability"] == "unknown"
    assert snapshot["jobs"] == {
        "available": True,
        "total": 3,
        "counts": {"pending": 1, "leased": 0, "done": 1, "failed": 1},
    }
    assert snapshot["research"]["total"] == 2
    assert snapshot["mint_locations"]["available"] is True
    assert snapshot["mint_locations"]["unique_exact_cas"] == 1
    assert snapshot["sources"]["bsc_factory_mints"]["last_processed_block"] == (
        115_824_174
    )
    assert snapshot["sources"]["bsc_factory_mints"]["finality"] == (
        "included_not_finalized"
    )
    latest = snapshot["research"]["recent_packages"]
    assert [item["package_id"] for item in latest] == ["package-2"]
    assert latest[0]["authorizes_trade"] is False
    assert "research" not in latest[0]

    configuration = snapshot["configuration"]
    assert configuration["x"]["source"] == "fxtwitter_public_api"
    assert configuration["debot"]["available"] is True
    assert configuration["grok"]["available"] is True
    raw = json.dumps(snapshot)
    for secret in (*env.values(), "research-body-2"):
        assert secret not in raw


def test_actor_cadence_matches_the_reviewed_monitor_and_skips_unverified_ids(
    tmp_path: Path,
) -> None:
    snapshot = status_snapshot(_settings(tmp_path), environ={}, clock=lambda: NOW)
    actors = {item["handle"]: item for item in snapshot["actors"]}

    assert actors["elonmusk"]["poll_seconds"] == 5.0
    assert actors["karpathy"]["poll_seconds"] == 10.0
    assert actors["btc2ai"]["poll_seconds"] == 5.0
    assert actors["jtitordemon2036"]["poll_seconds"] == 5.0
    assert actors["jtitordemon2036"]["monitor_reposts"] is True
    assert actors["jtitordemon2036"]["capabilities"] == []
    assert "four_meme" not in actors
    assert snapshot["polling"] == {
        "collector_tick_seconds": 0.25,
        "debot_seconds": 1.0,
        "mint_seconds": 1.0,
        "chain_mint_seconds": 0.25,
        "market_seconds": 5.0,
    }
    assert snapshot["configuration"]["market"]["source"] == (
        "coinmarketcap_exact_bsc_1h"
    )


def test_missing_or_wrong_schema_is_reported_without_creating_databases(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    snapshot = status_snapshot(settings, environ={}, clock=lambda: NOW)
    assert snapshot["jobs"]["available"] is False
    assert snapshot["research"]["available"] is False
    assert not settings.state_dir.exists()

    settings.state_dir.mkdir()
    settings.queue_database.write_bytes(b"not sqlite")
    snapshot = status_snapshot(settings, environ={}, clock=lambda: NOW)
    assert snapshot["jobs"]["available"] is False


def test_key_file_availability_reports_source_but_not_path_or_value(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path)
    key = tmp_path / "private-grok-key"
    key.write_text("file-secret", encoding="utf-8")
    snapshot = status_snapshot(
        settings,
        environ={"DEBOT4_GROK2API_KEY_FILE": str(key)},
        clock=lambda: NOW,
    )
    assert snapshot["configuration"]["grok"] == {
        "available": True, "source": "key_file", "credentials_exposed": False,
    }
    raw = json.dumps(snapshot)
    assert str(key) not in raw and "file-secret" not in raw


def test_private_telegram_config_reports_realtime_without_secrets(
    tmp_path: Path,
) -> None:
    session = tmp_path / "telegram.session"
    session.write_bytes(b"session")
    session.chmod(0o600)
    config = tmp_path / "telegram.json"
    secret_hash = "f" * 32
    config.write_text(json.dumps({
        "schema": "debot4.telegram-realtime.v1",
        "session_path": str(session),
        "api_id": 12345,
        "api_hash": secret_hash,
        "proxy": None,
    }), encoding="utf-8")
    config.chmod(0o600)
    settings = NarrativeSettings(
        tmp_path / "state", tmp_path / "debot-cookies.json",
        telegram_realtime_config=config,
    )

    snapshot = status_snapshot(settings, environ={}, clock=lambda: NOW)

    telegram = snapshot["configuration"]["telegram"]
    assert telegram["realtime"] is True
    assert telegram["source"] == "personal_session+public_html"
    raw = json.dumps(snapshot)
    assert secret_hash not in raw and str(config) not in raw
