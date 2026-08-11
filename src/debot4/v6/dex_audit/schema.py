"""Append-only schema for DEX ranking and DeBot coverage observations."""

from __future__ import annotations

import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS dex_audit_runs (
    run_id TEXT PRIMARY KEY,
    as_of_us INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    universe TEXT NOT NULL,
    ranking_exact INTEGER NOT NULL CHECK(ranking_exact IN (0, 1)),
    success INTEGER NOT NULL CHECK(success IN (0, 1)),
    failure_reason TEXT,
    ledger_available INTEGER NOT NULL CHECK(ledger_available IN (0, 1)),
    ledger_failure_reason TEXT,
    row_count INTEGER NOT NULL CHECK(row_count >= 0),
    inserted_at_us INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS dex_audit_runs_time_idx
ON dex_audit_runs(as_of_us DESC, run_id DESC);

CREATE TABLE IF NOT EXISTS dex_audit_attempts (
    run_id TEXT NOT NULL REFERENCES dex_audit_runs(run_id),
    attempt_no INTEGER NOT NULL CHECK(attempt_no > 0),
    source TEXT NOT NULL,
    method TEXT NOT NULL,
    url TEXT NOT NULL,
    request_json TEXT,
    started_at_us INTEGER NOT NULL,
    completed_at_us INTEGER NOT NULL,
    latency_ms INTEGER NOT NULL CHECK(latency_ms >= 0),
    http_status INTEGER,
    response_bytes INTEGER NOT NULL CHECK(response_bytes >= 0),
    success INTEGER NOT NULL CHECK(success IN (0, 1)),
    failure_reason TEXT,
    PRIMARY KEY(run_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS dex_audit_rows (
    run_id TEXT NOT NULL REFERENCES dex_audit_runs(run_id),
    rank INTEGER NOT NULL CHECK(rank > 0),
    as_of_us INTEGER NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL,
    token_address TEXT NOT NULL,
    pair_address TEXT,
    symbol TEXT NOT NULL,
    name TEXT NOT NULL,
    h1_change_pct TEXT NOT NULL,
    liquidity_usd TEXT,
    fdv_usd TEXT,
    market_cap_usd TEXT,
    price_usd TEXT,
    volume_h1_usd TEXT,
    txns_h1 INTEGER,
    debot_discovered INTEGER NOT NULL CHECK(debot_discovered IN (0, 1)),
    signal_id TEXT,
    signal_at_us INTEGER,
    debot_decided INTEGER NOT NULL CHECK(debot_decided IN (0, 1)),
    decision_id TEXT,
    decision_at_us INTEGER,
    decision_status TEXT,
    debot_bought INTEGER NOT NULL CHECK(debot_bought IN (0, 1)),
    buy_id TEXT,
    buy_at_us INTEGER,
    miss_reason TEXT NOT NULL,
    PRIMARY KEY(run_id, rank),
    UNIQUE(run_id, token_address)
);
CREATE INDEX IF NOT EXISTS dex_audit_rows_token_time_idx
ON dex_audit_rows(token_address, as_of_us DESC);
"""


TABLES = ("dex_audit_runs", "dex_audit_attempts", "dex_audit_rows")


def install_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    for table in TABLES:
        connection.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} UPDATE is forbidden'); END;
            CREATE TRIGGER IF NOT EXISTS {table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} DELETE is forbidden'); END;
            """
        )
