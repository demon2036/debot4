"""Atomic private following snapshots keyed by stable actor ID."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile

from .models import AuthorityNode, FollowingSnapshot


_SCHEMA = "debot4.following_snapshots.v1"


class JsonFollowingSnapshotStore:
    def __init__(self, path: str | Path, *, max_actors: int = 200) -> None:
        if not 1 <= max_actors <= 2_000:
            raise ValueError("following snapshot actor limit is invalid")
        self.path = Path(path).expanduser().resolve()
        self.max_actors = max_actors
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        self._items = self._read()

    def load(self, actor_id: str) -> FollowingSnapshot | None:
        return self._items.get(actor_id.strip())

    def save(self, snapshot: FollowingSnapshot) -> None:
        items = dict(self._items)
        actor_id = snapshot.actor.user_id
        if actor_id not in items and len(items) >= self.max_actors:
            raise ValueError("following snapshot actor limit exceeded")
        items[actor_id] = snapshot
        self._write(items)
        self._items = items

    def _read(self) -> dict[str, FollowingSnapshot]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError("following snapshot file is invalid") from exc
        rows = raw.get("actors") if isinstance(raw, dict) and raw.get("schema") == _SCHEMA else None
        if not isinstance(rows, dict) or len(rows) > self.max_actors:
            raise ValueError("following snapshot collection is invalid")
        output: dict[str, FollowingSnapshot] = {}
        for key, item in rows.items():
            snapshot = _snapshot(item)
            if key != snapshot.actor.user_id or key in output:
                raise ValueError("following snapshot key mismatch")
            output[key] = snapshot
        return output

    def _write(self, items: dict[str, FollowingSnapshot]) -> None:
        payload = json.dumps(
            {"schema": _SCHEMA, "actors": {key: value.as_dict() for key, value in sorted(items.items())}},
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


def _snapshot(value: object) -> FollowingSnapshot:
    if not isinstance(value, dict) or not isinstance(value.get("actor"), dict):
        raise ValueError("following snapshot entry is invalid")
    actor = value["actor"]
    following = value.get("following")
    if not isinstance(following, dict):
        raise ValueError("following snapshot entry is invalid")
    return FollowingSnapshot(
        actor=AuthorityNode(
            str(actor.get("handle") or ""), str(actor.get("user_id") or ""),
            str(actor.get("display_name") or ""), str(actor.get("role") or ""),
            str(actor.get("evidence_url") or ""),
        ),
        observed_at=datetime.fromisoformat(str(value.get("observed_at") or "")),
        source_url=str(value.get("source_url") or ""),
        evidence_hash=str(value.get("evidence_hash") or ""),
        following={str(key): str(item) for key, item in following.items()},
        page_count=int(value.get("page_count") or 0),
    )
