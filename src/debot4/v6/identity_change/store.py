"""Atomic private profile snapshots keyed by normalized X handle."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from .models import ProfileSnapshot


_SCHEMA = "debot4.identity_profile_snapshots.v1"


class JsonProfileSnapshotStore:
    def __init__(self, path: str | Path, *, max_profiles: int = 1_000) -> None:
        if not 1 <= max_profiles <= 10_000:
            raise ValueError("profile snapshot limit is invalid")
        self.path = Path(path).expanduser().resolve()
        self.max_profiles = max_profiles
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self._items = self._read()

    def load(self, handle: str) -> ProfileSnapshot | None:
        return self._items.get(handle.strip().lstrip("@").casefold())

    def save(self, snapshot: ProfileSnapshot) -> None:
        items = dict(self._items)
        if snapshot.handle not in items and len(items) >= self.max_profiles:
            raise ValueError("profile snapshot limit exceeded")
        items[snapshot.handle] = snapshot
        self._write(items)
        self._items = items

    def _read(self) -> dict[str, ProfileSnapshot]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("profile snapshot file is invalid") from exc
        if not isinstance(raw, dict) or raw.get("schema") != _SCHEMA:
            raise ValueError("profile snapshot schema is invalid")
        profiles = raw.get("profiles")
        if not isinstance(profiles, dict) or len(profiles) > self.max_profiles:
            raise ValueError("profile snapshot collection is invalid")
        output: dict[str, ProfileSnapshot] = {}
        for key, item in profiles.items():
            if not isinstance(item, dict) or not isinstance(item.get("state"), dict):
                raise ValueError("profile snapshot entry is invalid")
            snapshot = ProfileSnapshot(
                handle=str(item.get("handle") or ""),
                user_id=str(item.get("user_id") or ""),
                observed_at=datetime.fromisoformat(str(item.get("observed_at") or "")),
                source_url=str(item.get("source_url") or ""),
                evidence_hash=str(item.get("evidence_hash") or ""),
                state=item["state"],
            )
            if key != snapshot.handle or key in output:
                raise ValueError("profile snapshot key mismatch")
            output[key] = snapshot
        return output

    def _write(self, items: dict[str, ProfileSnapshot]) -> None:
        payload = json.dumps(
            {"schema": _SCHEMA, "profiles": {
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
