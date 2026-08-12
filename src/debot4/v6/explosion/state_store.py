"""Small private state store used by finite explosion monitors."""

from __future__ import annotations

import fcntl
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Mapping, TextIO


Scalar = str | int | float | bool | None
_SCHEMA = "debot4.explosion_monitor_state.v1"


class JsonEvidenceStateStore:
    """Atomically persist flat observations without coupling rules to storage."""

    def __init__(self, path: str | Path, *, namespace: str, max_entries: int = 10_000) -> None:
        if not namespace.strip() or not 1 <= max_entries <= 100_000:
            raise ValueError("explosion state configuration is invalid")
        self.path = Path(path).expanduser().resolve()
        self.namespace = namespace.strip().casefold()
        self.max_entries = max_entries
        self.lock_path = self.path.with_name(f".{self.path.name}.lock")
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)

    def load(self, key: str) -> dict[str, Scalar] | None:
        normalized = _key(key)
        with self._lock(shared=True):
            item = self._read().get(normalized)
        return dict(item) if item is not None else None

    def save(self, key: str, value: Mapping[str, object]) -> None:
        normalized = _key(key)
        clean = _flat(value)
        with self._lock(shared=False):
            items = self._read()
            if normalized not in items and len(items) >= self.max_entries:
                raise ValueError("explosion state entry limit exceeded")
            items[normalized] = clean
            self._write(items)

    def count(self) -> int:
        with self._lock(shared=True):
            return len(self._read())

    def _lock(self, *, shared: bool):
        stream = self.lock_path.open("a+", encoding="utf-8")
        self.lock_path.chmod(0o600)
        fcntl.flock(stream.fileno(), fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        return _LockedFile(stream)

    def _read(self) -> dict[str, dict[str, Scalar]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("explosion state file is invalid") from exc
        if (
            not isinstance(raw, dict)
            or raw.get("schema") != _SCHEMA
            or raw.get("namespace") != self.namespace
        ):
            raise ValueError("explosion state schema is invalid")
        rows = raw.get("items")
        if not isinstance(rows, dict) or len(rows) > self.max_entries:
            raise ValueError("explosion state collection is invalid")
        output: dict[str, dict[str, Scalar]] = {}
        for key, value in rows.items():
            if key != _key(key) or key in output or not isinstance(value, dict):
                raise ValueError("explosion state entry is invalid")
            output[key] = _flat(value)
        return output

    def _write(self, items: Mapping[str, Mapping[str, Scalar]]) -> None:
        payload = json.dumps(
            {"schema": _SCHEMA, "namespace": self.namespace, "items": items},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
            ) as stream:
                temporary = Path(stream.name)
                temporary.chmod(0o600)
                stream.write(payload + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()


class _LockedFile:
    def __init__(self, stream: TextIO) -> None:
        self.stream = stream

    def __enter__(self) -> TextIO:
        return self.stream

    def __exit__(self, *_args: object) -> None:
        fcntl.flock(self.stream.fileno(), fcntl.LOCK_UN)
        self.stream.close()


def _key(value: str) -> str:
    clean = value.strip().casefold()
    if not clean or len(clean) > 512 or any(character in clean for character in "\r\n"):
        raise ValueError("explosion state key is invalid")
    return clean


def _flat(value: Mapping[str, object]) -> dict[str, Scalar]:
    output: dict[str, Scalar] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("explosion state field is invalid")
        if not isinstance(item, (str, int, float, bool, type(None))):
            raise ValueError("explosion state must be a flat JSON object")
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError("explosion state number must be finite")
        output[key] = item
    return output
