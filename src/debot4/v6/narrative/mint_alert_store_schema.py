"""SQLite schema and additive migration for the mint-alert outbox."""

from __future__ import annotations

import sqlite3


TABLE = "catalyst_mint_alerts"
SCHEMA_VERSION = 3
INSERT_COLUMNS = """
alert_id,match_id,exact_ca,token_stage,match_kind,catalyst_tweet_id,catalyst_author,
catalyst_text,catalyst_created_at,catalyst_fetched_at,token_created_at,
match_observed_at,token_name,token_symbol,provider_fdv_usd,launchpad,
token_description,token_social_urls_json,token_status_url,raised_at,next_attempt_at,
decision_reason,qualification_model,qualified_at
"""
SCHEMA = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    alert_id TEXT PRIMARY KEY,
    match_id TEXT NOT NULL UNIQUE,
    exact_ca TEXT NOT NULL UNIQUE,
    token_stage TEXT NOT NULL,
    match_kind TEXT NOT NULL,
    catalyst_tweet_id TEXT NOT NULL,
    catalyst_author TEXT NOT NULL,
    catalyst_text TEXT NOT NULL,
    catalyst_created_at TEXT NOT NULL,
    catalyst_fetched_at TEXT NOT NULL,
    token_created_at TEXT NOT NULL,
    match_observed_at TEXT NOT NULL,
    token_name TEXT,
    token_symbol TEXT,
    provider_fdv_usd TEXT,
    launchpad TEXT,
    token_description TEXT,
    token_social_urls_json TEXT NOT NULL,
    token_status_url TEXT NOT NULL,
    raised_at TEXT NOT NULL,
    delivery_attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_delivery_error_type TEXT,
    delivered_at TEXT,
    authorizes_trade INTEGER NOT NULL DEFAULT 0 CHECK(authorizes_trade = 0),
    decision_reason TEXT NOT NULL DEFAULT 'legacy_unqualified_alert',
    qualification_model TEXT,
    qualified_at TEXT
);
CREATE INDEX IF NOT EXISTS catalyst_mint_alerts_delivery_idx
ON {TABLE}(delivered_at,next_attempt_at,catalyst_created_at);
CREATE INDEX IF NOT EXISTS catalyst_mint_alerts_raised_idx
ON {TABLE}(raised_at DESC,alert_id DESC);
"""
_MIGRATION_COLUMNS = {
    "decision_reason": (
        "TEXT NOT NULL DEFAULT 'legacy_unqualified_alert'"
    ),
    "qualification_model": "TEXT",
    "qualified_at": "TEXT",
}


def prepare_mint_alert_schema(database: sqlite3.Connection) -> None:
    version = int(database.execute("PRAGMA user_version").fetchone()[0])
    if version > SCHEMA_VERSION:
        raise RuntimeError("mint alert database schema is newer than this runtime")
    database.executescript(SCHEMA)
    columns = {
        str(row[1]) for row in database.execute(f"PRAGMA table_info({TABLE})")
    }
    for name, declaration in _MIGRATION_COLUMNS.items():
        if name not in columns:
            database.execute(
                f"ALTER TABLE {TABLE} ADD COLUMN {name} {declaration}"
            )
    database.execute(f"PRAGMA user_version={SCHEMA_VERSION}")


__all__ = ["INSERT_COLUMNS", "SCHEMA", "TABLE", "prepare_mint_alert_schema"]
