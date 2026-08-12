"""Atomic private snapshots for official public product resources."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from .rules import PublicResourceSnapshot


_SCHEMA = "debot4.public_resource_snapshots.v1"


class JsonPublicResourceSnapshotStore:
    def __init__(self, path: str | Path, *, max_resources: int = 500) -> None:
        if not 1 <= max_resources <= 5_000:
            raise ValueError("public resource snapshot limit is invalid")
        self.path = Path(path).expanduser().resolve()
        self.max_resources = max_resources
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self._items = self._read()

    def load(self, resource_id: str) -> PublicResourceSnapshot | None:
        return self._items.get(resource_id.strip().casefold())

    def save(self, snapshot: PublicResourceSnapshot) -> None:
        items = dict(self._items)
        if snapshot.resource_id not in items and len(items) >= self.max_resources:
            raise ValueError("public resource snapshot limit exceeded")
        items[snapshot.resource_id] = snapshot
        self._write(items)
        self._items = items

    def _read(self) -> dict[str, PublicResourceSnapshot]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("public resource snapshot file is invalid") from exc
        if not isinstance(raw, dict) or raw.get("schema") != _SCHEMA:
            raise ValueError("public resource snapshot schema is invalid")
        rows = raw.get("resources")
        if not isinstance(rows, dict) or len(rows) > self.max_resources:
            raise ValueError("public resource snapshot collection is invalid")
        output: dict[str, PublicResourceSnapshot] = {}
        for key, row in rows.items():
            if not isinstance(row, dict):
                raise ValueError("public resource snapshot entry is invalid")
            item = PublicResourceSnapshot(
                resource_id=str(row.get("resource_id") or ""),
                actor_id=str(row.get("actor_id") or ""),
                actor_role=str(row.get("actor_role") or ""),
                observed_at=datetime.fromisoformat(str(row.get("observed_at") or "")),
                source_url=str(row.get("source_url") or ""),
                evidence_hash=str(row.get("evidence_hash") or ""),
                terms=frozenset(_strings(row, "terms")),
                token_addresses=frozenset(_strings(row, "token_addresses")),
                artifacts=frozenset(_strings(row, "artifacts")),
                title=str(row.get("title") or ""),
                retrieved_url=str(row.get("retrieved_url") or row.get("source_url") or ""),
            )
            if key != item.resource_id or key in output:
                raise ValueError("public resource snapshot key mismatch")
            output[key] = item
        return output

    def _write(self, items: dict[str, PublicResourceSnapshot]) -> None:
        payload = json.dumps(
            {"schema": _SCHEMA, "resources": {
                key: item.as_dict() for key, item in sorted(items.items())
            }},
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


def _strings(row: dict[str, object], key: str) -> tuple[str, ...]:
    values = row.get(key)
    if not isinstance(values, list) or any(not isinstance(item, str) for item in values):
        raise ValueError("public resource snapshot list is invalid")
    return tuple(values)
