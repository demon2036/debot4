"""Versioned SQLite schema and lossless queue migrations."""

from __future__ import annotations

import sqlite3


QUEUE_SCHEMA_VERSION = 4

TABLE_SQL = """
CREATE TABLE narrative_jobs (
    job_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN (
        'active_x_post','active_telegram_post','passive_debot_signal',
        'passive_market_anomaly','passive_catalyst_mint'
    )),
    priority INTEGER NOT NULL DEFAULT 50 CHECK(priority BETWEEN 1 AND 100),
    content_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('pending','leased','done','failed')),
    attempts INTEGER NOT NULL CHECK(attempts >= 0),
    max_attempts INTEGER NOT NULL CHECK(max_attempts BETWEEN 1 AND 100),
    available_at TEXT NOT NULL,
    lease_owner TEXT,
    lease_id TEXT,
    lease_expires_at TEXT,
    error_type TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK((status = 'leased') =
          (lease_owner IS NOT NULL AND lease_id IS NOT NULL
           AND lease_expires_at IS NOT NULL)),
    CHECK((status IN ('done','failed')) = (completed_at IS NOT NULL))
)
"""

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS narrative_jobs_claim_idx
ON narrative_jobs(status, priority, available_at, created_at, job_id)
"""

SCHEMA = f"{TABLE_SQL};\n{INDEX_SQL};\nPRAGMA user_version={QUEUE_SCHEMA_VERSION};"


def prepare_queue_schema(db: sqlite3.Connection) -> None:
    """Create v4 or rebuild an older schema without dropping queued work."""

    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='narrative_jobs'"
    ).fetchone()
    if row is None:
        _create(db)
        return
    columns = {
        str(item[1]) for item in db.execute("PRAGMA table_info(narrative_jobs)")
    }
    sql = str(row[0] or "").casefold()
    if "priority" in columns and "passive_catalyst_mint" in sql:
        db.execute(INDEX_SQL)
        db.execute(f"PRAGMA user_version={QUEUE_SCHEMA_VERSION}")
        return
    _migrate_legacy(db, columns)


def _create(db: sqlite3.Connection) -> None:
    db.execute(TABLE_SQL)
    db.execute(INDEX_SQL)
    db.execute(f"PRAGMA user_version={QUEUE_SCHEMA_VERSION}")


def _migrate_legacy(db: sqlite3.Connection, columns: set[str]) -> None:
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute("DROP INDEX IF EXISTS narrative_jobs_claim_idx")
        db.execute("ALTER TABLE narrative_jobs RENAME TO narrative_jobs_legacy")
        db.execute(TABLE_SQL)
        priority = "priority" if "priority" in columns else "50"
        db.execute(
            "INSERT INTO narrative_jobs "
            "(job_id,kind,priority,content_sha256,payload_json,status,attempts,"
            "max_attempts,available_at,lease_owner,lease_id,lease_expires_at,"
            "error_type,created_at,updated_at,completed_at) "
            f"SELECT job_id,kind,{priority},content_sha256,payload_json,status,attempts,"
            "max_attempts,available_at,lease_owner,lease_id,lease_expires_at,"
            "error_type,created_at,updated_at,completed_at "
            "FROM narrative_jobs_legacy"
        )
        db.execute("DROP TABLE narrative_jobs_legacy")
        db.execute(INDEX_SQL)
        db.execute(f"PRAGMA user_version={QUEUE_SCHEMA_VERSION}")
        db.execute("COMMIT")
    except BaseException:
        db.execute("ROLLBACK")
        raise
