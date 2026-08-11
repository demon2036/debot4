"""Thread-safe service health state exposed to the dashboard."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from .identity import json_safe


UTC = timezone.utc


class RuntimeState:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._data: dict[str, Any] = {
            "status": "starting",
            "started_at": datetime.now(UTC),
            "bootstrapped": False,
            "signals_seen": 0,
            "signals_queued": 0,
            "decisions": 0,
            "buys": 0,
            "rejects": 0,
            "errors": 0,
            "active_buys": 0,
            "completed_outcomes": 0,
        }
        self._persist()

    def update(self, **fields: Any) -> None:
        with self._lock:
            self._data.update(fields)
            self._data["updated_at"] = datetime.now(UTC)
            self._persist_locked()

    def increment(self, field: str, amount: int = 1, **fields: Any) -> None:
        with self._lock:
            self._data[field] = int(self._data.get(field, 0)) + amount
            self._data.update(fields)
            self._data["updated_at"] = datetime.now(UTC)
            self._persist_locked()

    def error(self, message: str) -> None:
        self.increment("errors", last_error=str(message)[:500])

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return json_safe(dict(self._data))

    def _persist(self) -> None:
        with self._lock:
            self._persist_locked()

    def _persist_locked(self) -> None:
        payload = json.dumps(
            json_safe(self._data), ensure_ascii=False, sort_keys=True, indent=2
        )
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload + "\n", encoding="utf-8")
        os.replace(temporary, self.path)
