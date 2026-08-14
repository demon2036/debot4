"""Read-only operational status for the narrative research runtime."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3
import stat
from typing import Any

from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY
from .monitor import TierPollingPolicy
from .mint_alert_delivery import DEFAULT_ALERT_POLL_SECONDS
from .mint_alert_status import read_mint_alert_status
from .mint_location_status import read_mint_location_status
from .research_status import summarize_research_document
from .settings import NarrativeSettings
from .source_status import read_source_checkpoints
from ..debot.credentials import DeBotCredentialError, load_debot_cookies
from ..telegram import load_telegram_realtime_config


JOB_STATUSES = ("pending", "leased", "done", "failed")
STATUS_SCHEMA = "debot4.v6.narrative_status.v4"


def status_snapshot(
    settings: NarrativeSettings | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
    recent_limit: int = 10,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Build a credential-free snapshot without creating or changing state."""

    if isinstance(recent_limit, bool) or not 1 <= recent_limit <= 100:
        raise ValueError("recent_limit must be between 1 and 100")
    env = os.environ if environ is None else environ
    current = settings or NarrativeSettings.from_env(env)
    now = (clock or (lambda: datetime.now(timezone.utc)))()
    if now.tzinfo is None:
        raise ValueError("status clock must return a timezone-aware datetime")
    checkpoints = read_source_checkpoints(current)
    actors = _monitored_actors(registry, checkpoints.x_latest_status_ids)
    return {
        "schema": STATUS_SCHEMA,
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "mode": "research_only",
        "research_only": True,
        "read_only": True,
        "authorizes_trade": False,
        "profitability": "unknown",
        "polling": {
            "collector_tick_seconds": current.collector_tick_seconds,
            "debot_seconds": current.debot_poll_seconds,
            "mint_seconds": current.mint_poll_seconds,
            "chain_mint_seconds": (
                current.chain_mint_poll_seconds
                if current.chain_mint_audit_enabled else None
            ),
            "mint_alert_seconds": DEFAULT_ALERT_POLL_SECONDS,
            "market_seconds": current.market_poll_seconds,
        },
        "actors": actors,
        "actor_count": len(actors),
        "sources": {
            key: dict(value) for key, value in checkpoints.public.items()
        },
        "configuration": _configuration(current, env),
        "jobs": _job_status(current.queue_database),
        "mint_locations": read_mint_location_status(
            current.mint_location_database
        ),
        "mint_alerts": read_mint_alert_status(current.mint_alert_database),
        "research": _research_status(current.research_database, recent_limit),
    }


def _monitored_actors(
    registry: ActorRegistry, latest_status_ids: Mapping[str, str]
) -> list[dict[str, Any]]:
    policy = TierPollingPolicy()
    actors = []
    for registration in registry.registrations():
        if not registration.author_ids:
            continue
        actor = registration.actor
        latest_id = latest_status_ids.get(actor.handle.casefold(), "")
        actors.append({
            "handle": actor.handle,
            "display_name": actor.display_name,
            "role": actor.role,
            "author_id": registration.author_ids[0],
            "identity_verified": True,
            "tier": actor.tier.value,
            "priority": actor.priority,
            "monitor_x": actor.monitor_x,
            "monitor_reposts": actor.monitor_reposts,
            "poll_seconds": (
                policy.interval_for(actor.tier, actor.priority)
                if actor.monitor_x else None
            ),
            "ecosystems": list(actor.ecosystems),
            "languages": list(actor.languages),
            "regions": list(actor.regions),
            "capabilities": [item.value for item in actor.capabilities],
            "telegram_channels": list(actor.telegram_channels),
            "checkpointed": actor.handle.casefold() in latest_status_ids,
            "latest_status_url": (
                f"https://x.com/{actor.handle}/status/{latest_id}"
                if latest_id else ""
            ),
        })
    return sorted(actors, key=lambda item: (
        item["poll_seconds"] is None,
        item["poll_seconds"] or 999.0,
        item["priority"],
        item["handle"].casefold(),
    ))


def _job_status(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "total": 0,
        "counts": {status: 0 for status in JOB_STATUSES},
    }
    try:
        with _read_only(path) as database:
            rows = database.execute(
                "SELECT status, COUNT(*) AS total FROM narrative_jobs GROUP BY status"
            ).fetchall()
    except (OSError, sqlite3.Error):
        return result
    for row in rows:
        status = str(row["status"])
        if status in result["counts"]:
            result["counts"][status] = int(row["total"])
    result["available"] = True
    result["total"] = sum(result["counts"].values())
    return result


def _research_status(path: Path, limit: int) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": False,
        "total": 0,
        "recent_packages": [],
    }
    try:
        with _read_only(path) as database:
            total = database.execute(
                "SELECT COUNT(*) AS total FROM narrative_research_packages"
            ).fetchone()
            rows = database.execute(
                "SELECT package_id,mode,trigger_id,triggered_at,researched_at,"
                "status,reason,document_json FROM narrative_research_packages "
                "ORDER BY researched_at DESC,package_id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    except (OSError, sqlite3.Error):
        return result
    result["available"] = True
    result["total"] = 0 if total is None else int(total["total"])
    result["recent_packages"] = [
        {
            "package_id": row["package_id"],
            "mode": row["mode"],
            "trigger_id": row["trigger_id"],
            "triggered_at": row["triggered_at"],
            "researched_at": row["researched_at"],
            "status": row["status"],
            "reason": row["reason"],
            "research_only": True,
            "authorizes_trade": False,
            **summarize_research_document(row["document_json"]),
        }
        for row in rows
    ]
    return result


def _read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path.name)
    database = sqlite3.connect(
        f"{path.resolve().as_uri()}?mode=ro", uri=True, timeout=1
    )
    database.row_factory = sqlite3.Row
    database.execute("PRAGMA query_only=ON")
    return database


def _configuration(
    settings: NarrativeSettings, env: Mapping[str, str]
) -> dict[str, dict[str, Any]]:
    debot_ready = _debot_credentials_ready(settings.debot_cookie_file)
    grok_source = _grok_source(env)
    telegram_realtime = _telegram_realtime_ready(settings.telegram_realtime_config)
    return {
        "x": _availability(True, "fxtwitter_public_api"),
        "telegram": {
            **_availability(
                True,
                "personal_session+public_html"
                if telegram_realtime else "public_html",
            ),
            "realtime": telegram_realtime,
        },
        "debot": _availability(
            debot_ready, "private_cookie_file" if debot_ready else "none"
        ),
        "market": _availability(True, "coinmarketcap_exact_bsc_1h"),
        "bsc_mint": _availability(
            settings.chain_mint_audit_enabled,
            (
                "bsc_zero_transfer_known_launchpad_suffixes"
                if settings.chain_mint_audit_enabled else "disabled"
            ),
        ),
        "mint_alert": _availability(True, "durable_sqlite_jsonl"),
        "grok": _availability(grok_source != "none", grok_source),
    }


def _availability(available: bool, source: str) -> dict[str, Any]:
    return {
        "available": available,
        "source": source,
        "credentials_exposed": False,
    }


def _debot_credentials_ready(path: Path) -> bool:
    try:
        return bool(load_debot_cookies(path))
    except (OSError, DeBotCredentialError):
        return False


def _grok_source(env: Mapping[str, str]) -> str:
    if env.get("DEBOT4_GROK2API_KEY", "").strip():
        return "environment"
    raw_path = env.get("DEBOT4_GROK2API_KEY_FILE", "").strip()
    if not raw_path:
        return "none"
    try:
        path = Path(raw_path)
        metadata = path.stat()
        if not stat.S_ISREG(metadata.st_mode) or not 0 < metadata.st_size <= 4096:
            return "none"
        return "key_file" if path.read_bytes().strip() else "none"
    except OSError:
        return "none"


def _telegram_realtime_ready(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        load_telegram_realtime_config(path)
    except (OSError, ValueError):
        return False
    return True
