PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -32768;
PRAGMA mmap_size = 0;
PRAGMA busy_timeout = 5000;
PRAGMA wal_autocheckpoint = 1000;

CREATE TABLE IF NOT EXISTS events (
    sequence        INTEGER PRIMARY KEY,
    source          TEXT NOT NULL CHECK (length(source) BETWEEN 1 AND 128),
    dedupe_key      TEXT NOT NULL CHECK (length(dedupe_key) BETWEEN 1 AND 512),
    event_type      TEXT NOT NULL CHECK (length(event_type) BETWEEN 1 AND 128),
    subject         TEXT NOT NULL CHECK (length(subject) BETWEEN 1 AND 512),
    occurred_at_us  INTEGER NOT NULL CHECK (occurred_at_us >= 0),
    observed_at_us  INTEGER NOT NULL CHECK (observed_at_us >= 0),
    available_at_us INTEGER NOT NULL CHECK (available_at_us >= observed_at_us),
    payload_json    TEXT NOT NULL,
    content_hash    TEXT NOT NULL CHECK (length(content_hash) = 64),
    inserted_at_us  INTEGER NOT NULL CHECK (inserted_at_us >= 0),
    UNIQUE (source, dedupe_key)
) STRICT;

CREATE INDEX IF NOT EXISTS events_available_idx
    ON events (available_at_us, sequence);

CREATE INDEX IF NOT EXISTS events_source_type_available_idx
    ON events (source, event_type, available_at_us, sequence);

CREATE INDEX IF NOT EXISTS events_subject_occurred_idx
    ON events (subject, occurred_at_us, sequence);

CREATE INDEX IF NOT EXISTS events_subject_type_available_idx
    ON events (subject, event_type, available_at_us DESC, sequence DESC);

CREATE TRIGGER IF NOT EXISTS events_reject_replacement
BEFORE INSERT ON events
WHEN EXISTS (
    SELECT 1
    FROM events
    WHERE (NEW.sequence >= 0 AND sequence = NEW.sequence)
       OR (source = NEW.source AND dedupe_key = NEW.dedupe_key)
)
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: replacement is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS events_reject_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: UPDATE is forbidden');
END;

CREATE TRIGGER IF NOT EXISTS events_reject_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events are append-only: DELETE is forbidden');
END;
