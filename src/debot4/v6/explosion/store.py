"""Private append-only SQLite store for idempotent explosion evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sqlite3

from .models import ExplosionEvent


_SCHEMA = """
CREATE TABLE IF NOT EXISTS explosion_events (
    event_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    subtype TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    subject TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS explosion_events_time
ON explosion_events(first_seen_at, event_id);
"""


class ExplosionEventStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self._connection = sqlite3.connect(self.path, timeout=5)
        self._connection.executescript(_SCHEMA)
        self._connection.commit()
        self.path.chmod(0o600)

    def __enter__(self) -> "ExplosionEventStore":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()

    def close(self) -> None:
        self._connection.close()

    def append(self, event: ExplosionEvent) -> bool:
        payload = json.dumps(
            event.as_public_dict(), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        )
        cursor = self._connection.execute(
            """INSERT OR IGNORE INTO explosion_events
            (event_id, category, subtype, occurred_at, first_seen_at,
             subject, actor_id, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.event_id, event.category.value, event.subtype,
                event.occurred_at.isoformat(), event.first_seen_at.isoformat(),
                event.subject, event.actor_id, payload,
            ),
        )
        self._connection.commit()
        return cursor.rowcount == 1

    def count(self) -> int:
        row = self._connection.execute(
            "SELECT COUNT(*) FROM explosion_events"
        ).fetchone()
        return int(row[0])

    def recent(self, limit: int = 100) -> tuple[dict[str, object], ...]:
        if isinstance(limit, bool) or not 1 <= limit <= 1_000:
            raise ValueError("event limit must be between 1 and 1000")
        rows = self._connection.execute(
            """SELECT payload_json FROM explosion_events
            ORDER BY first_seen_at DESC, event_id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return tuple(json.loads(row[0]) for row in rows)
