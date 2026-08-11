"""Schema v2 for the independent append-only v6 ledger."""

from __future__ import annotations

import sqlite3


SCHEMA = """
CREATE TABLE IF NOT EXISTS v6_commits (
    commit_seq INTEGER PRIMARY KEY AUTOINCREMENT,
    committed_at_us INTEGER NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS v6_candidates (
    candidate_id TEXT PRIMARY KEY, chain TEXT NOT NULL,
    token_address TEXT NOT NULL, detected_at_us INTEGER NOT NULL,
    available_at_us INTEGER NOT NULL, source TEXT NOT NULL,
    evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL,
    CHECK(detected_at_us <= available_at_us)
);
CREATE INDEX IF NOT EXISTS v6_candidates_token_time_idx
ON v6_candidates(chain, token_address, detected_at_us, candidate_id);

CREATE TABLE IF NOT EXISTS v6_current_signals (
    signal_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES v6_candidates(candidate_id),
    chain TEXT NOT NULL, token_address TEXT NOT NULL,
    event_at_us INTEGER NOT NULL, available_at_us INTEGER NOT NULL,
    signal_kind TEXT NOT NULL, source TEXT NOT NULL,
    evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL,
    CHECK(event_at_us <= available_at_us)
);
CREATE INDEX IF NOT EXISTS v6_signals_candidate_time_idx
ON v6_current_signals(candidate_id, event_at_us DESC, available_at_us DESC);

CREATE TABLE IF NOT EXISTS v6_kol_evidence (
    evidence_id TEXT PRIMARY KEY, chain TEXT NOT NULL,
    token_address TEXT NOT NULL, signal_id TEXT NOT NULL,
    event_at_us INTEGER NOT NULL, available_at_us INTEGER NOT NULL,
    qualified_at_us INTEGER NOT NULL, source TEXT NOT NULL,
    evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL,
    CHECK(event_at_us <= available_at_us),
    CHECK(available_at_us <= qualified_at_us)
);
CREATE INDEX IF NOT EXISTS v6_kol_token_time_idx
ON v6_kol_evidence(chain, token_address, event_at_us DESC, evidence_id);

CREATE TABLE IF NOT EXISTS v6_entry_decisions (
    decision_id TEXT PRIMARY KEY,
    candidate_id TEXT NOT NULL REFERENCES v6_candidates(candidate_id),
    signal_id TEXT NOT NULL REFERENCES v6_current_signals(signal_id),
    kol_evidence_id TEXT REFERENCES v6_kol_evidence(evidence_id),
    decided_at_us INTEGER NOT NULL, status TEXT NOT NULL, reason TEXT NOT NULL,
    source TEXT NOT NULL, strategy_version TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS v6_simulated_buys (
    buy_id TEXT PRIMARY KEY,
    decision_id TEXT NOT NULL UNIQUE REFERENCES v6_entry_decisions(decision_id),
    candidate_id TEXT NOT NULL REFERENCES v6_candidates(candidate_id),
    signal_id TEXT NOT NULL REFERENCES v6_current_signals(signal_id),
    chain TEXT NOT NULL, token_address TEXT NOT NULL,
    executed_at_us INTEGER NOT NULL,
    block_number INTEGER NOT NULL CHECK(block_number >= 0),
    block_hash TEXT NOT NULL, entry_fdv_usd TEXT NOT NULL,
    notional_usd TEXT NOT NULL, entry_position_value_usd TEXT NOT NULL,
    source TEXT NOT NULL, evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS v6_buys_time_idx
ON v6_simulated_buys(executed_at_us, buy_id);

CREATE TABLE IF NOT EXISTS v6_block_observations (
    observation_id TEXT PRIMARY KEY,
    buy_id TEXT NOT NULL REFERENCES v6_simulated_buys(buy_id),
    block_number INTEGER NOT NULL CHECK(block_number >= 0),
    block_hash TEXT NOT NULL, parent_hash TEXT NOT NULL,
    observed_at_us INTEGER NOT NULL, available_at_us INTEGER NOT NULL,
    fdv_usd TEXT NOT NULL, position_value_usd TEXT NOT NULL,
    source TEXT NOT NULL, evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL,
    UNIQUE(buy_id, block_hash), CHECK(observed_at_us <= available_at_us)
);
CREATE INDEX IF NOT EXISTS v6_observations_buy_time_idx
ON v6_block_observations(buy_id, observed_at_us, block_number);

CREATE TABLE IF NOT EXISTS v6_head_sightings (
    sighting_id TEXT PRIMARY KEY,
    buy_id TEXT NOT NULL, block_number INTEGER NOT NULL CHECK(block_number >= 0),
    block_hash TEXT NOT NULL, sighted_at_us INTEGER NOT NULL,
    available_at_us INTEGER NOT NULL, source TEXT NOT NULL,
    evidence_uri TEXT NOT NULL, metadata_json TEXT NOT NULL,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL,
    UNIQUE(buy_id, block_hash, sighted_at_us),
    FOREIGN KEY(buy_id, block_hash)
        REFERENCES v6_block_observations(buy_id, block_hash),
    CHECK(sighted_at_us <= available_at_us)
);
CREATE INDEX IF NOT EXISTS v6_heads_buy_commit_idx
ON v6_head_sightings(buy_id, commit_seq DESC, sighting_id DESC);

CREATE TABLE IF NOT EXISTS v6_one_hour_results (
    buy_id TEXT PRIMARY KEY REFERENCES v6_simulated_buys(buy_id),
    status TEXT NOT NULL CHECK(status IN ('complete', 'incomplete', 'invalidated')),
    reason TEXT, window_ends_at_us INTEGER NOT NULL, cutoff_at_us INTEGER NOT NULL,
    coverage_complete_through_us INTEGER NOT NULL,
    allowed_lateness_us INTEGER NOT NULL, observation_count INTEGER NOT NULL,
    max_gap_us INTEGER NOT NULL, max_allowed_gap_us INTEGER NOT NULL,
    peak_fdv_usd TEXT, peak_position_value_usd TEXT,
    peak_observed_at_us INTEGER, peak_block_number INTEGER,
    final_fdv_usd TEXT, final_position_value_usd TEXT,
    final_observed_at_us INTEGER, final_block_number INTEGER,
    peak_multiple TEXT, final_multiple TEXT, peak_pnl_usd TEXT, final_pnl_usd TEXT,
    commit_seq INTEGER NOT NULL REFERENCES v6_commits(commit_seq),
    inserted_at_us INTEGER NOT NULL
);
"""

IMMUTABLE_TABLES = (
    ("v6_commits", "commit_seq"), ("v6_candidates", "candidate_id"),
    ("v6_current_signals", "signal_id"), ("v6_kol_evidence", "evidence_id"),
    ("v6_entry_decisions", "decision_id"), ("v6_simulated_buys", "buy_id"),
    ("v6_block_observations", "observation_id"),
    ("v6_head_sightings", "sighting_id"), ("v6_one_hour_results", "buy_id"),
)


EXTRA_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS v6_commits_no_time_replace
BEFORE INSERT ON v6_commits WHEN EXISTS (
    SELECT 1 FROM v6_commits WHERE committed_at_us = NEW.committed_at_us
      AND commit_seq <> NEW.commit_seq)
BEGIN SELECT RAISE(ABORT, 'commit time identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS v6_buys_no_decision_replace
BEFORE INSERT ON v6_simulated_buys WHEN EXISTS (
    SELECT 1 FROM v6_simulated_buys WHERE decision_id = NEW.decision_id
      AND buy_id <> NEW.buy_id)
BEGIN SELECT RAISE(ABORT, 'BUY decision identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS v6_observations_no_hash_replace
BEFORE INSERT ON v6_block_observations WHEN EXISTS (
    SELECT 1 FROM v6_block_observations WHERE buy_id = NEW.buy_id
      AND block_hash = NEW.block_hash AND observation_id <> NEW.observation_id)
BEGIN SELECT RAISE(ABORT, 'observation hash identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS v6_heads_no_identity_replace
BEFORE INSERT ON v6_head_sightings WHEN EXISTS (
    SELECT 1 FROM v6_head_sightings WHERE buy_id = NEW.buy_id
      AND block_hash = NEW.block_hash AND sighted_at_us = NEW.sighted_at_us
      AND sighting_id <> NEW.sighting_id)
BEGIN SELECT RAISE(ABORT, 'head sighting identity is immutable'); END;
CREATE TRIGGER IF NOT EXISTS v6_heads_require_matching_observation
BEFORE INSERT ON v6_head_sightings WHEN NOT EXISTS (
    SELECT 1 FROM v6_block_observations WHERE buy_id = NEW.buy_id
      AND block_hash = NEW.block_hash AND block_number = NEW.block_number)
BEGIN SELECT RAISE(ABORT, 'head sighting does not match observation'); END;
CREATE TRIGGER IF NOT EXISTS v6_observations_no_insert_after_result
BEFORE INSERT ON v6_block_observations WHEN EXISTS (
    SELECT 1 FROM v6_one_hour_results WHERE buy_id = NEW.buy_id)
BEGIN SELECT RAISE(ABORT, 'one-hour result is finalized'); END;
CREATE TRIGGER IF NOT EXISTS v6_heads_no_insert_after_result
BEFORE INSERT ON v6_head_sightings WHEN EXISTS (
    SELECT 1 FROM v6_one_hour_results WHERE buy_id = NEW.buy_id)
BEGIN SELECT RAISE(ABORT, 'one-hour result is finalized'); END;
"""


def install_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(SCHEMA)
    for table, key in IMMUTABLE_TABLES:
        connection.executescript(
            f"""
            CREATE TRIGGER IF NOT EXISTS {table}_no_update
            BEFORE UPDATE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} UPDATE is forbidden'); END;
            CREATE TRIGGER IF NOT EXISTS {table}_no_delete
            BEFORE DELETE ON {table}
            BEGIN SELECT RAISE(ABORT, '{table} DELETE is forbidden'); END;
            CREATE TRIGGER IF NOT EXISTS {table}_no_replace
            BEFORE INSERT ON {table}
            WHEN EXISTS (SELECT 1 FROM {table} WHERE {key} = NEW.{key})
            BEGIN SELECT RAISE(ABORT, '{table} replacement is forbidden'); END;
            """
        )
    connection.executescript(EXTRA_TRIGGERS)
