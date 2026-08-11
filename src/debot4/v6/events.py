"""Bounded JSONL operational audit log."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any

from .identity import json_safe


UTC = timezone.utc


class EventLog:
    def __init__(self, path: str | Path, *, max_bytes: int = 16 * 1024 * 1024) -> None:
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def write(self, kind: str, **fields: Any) -> None:
        event = {
            "at": datetime.now(UTC).isoformat(),
            "kind": str(kind),
            **json_safe(fields),
        }
        line = json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n"
        with self._lock:
            self._rotate()
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(line)
                handle.flush()

    def _rotate(self) -> None:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return
        if size < self.max_bytes:
            return
        backup = self.path.with_suffix(self.path.suffix + ".1")
        try:
            backup.unlink()
        except FileNotFoundError:
            pass
        os.replace(self.path, backup)
