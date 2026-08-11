"""Private, restart-safe checkpoints for active X narrative monitoring."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from ..x import XCheckpoint


CHECKPOINT_SCHEMA = "debot4.v6.narrative_monitor.checkpoints.v1"
_ROOT_FIELDS = frozenset({"schema", "accounts"})
_ACCOUNT_FIELDS = frozenset({"handle", "user_id", "latest_tweet_id"})


class CheckpointFormatError(ValueError):
    """The persisted checkpoint document does not match the v6 schema."""


class JsonXCheckpointStore:
    """Atomically persist bounded X timeline cursors in a private JSON file."""

    def __init__(self, path: str | Path, *, max_accounts: int = 256) -> None:
        if not 1 <= max_accounts <= 10_000:
            raise ValueError("max_accounts must be between 1 and 10000")
        self.path = Path(path)
        self.max_accounts = max_accounts
        self._secure_parent()
        self._items = self._read()

    def load(self, handle: str) -> XCheckpoint | None:
        normalized = XCheckpoint(handle).handle
        return self._items.get(normalized)

    def save(self, checkpoint: XCheckpoint) -> None:
        items = dict(self._items)
        if checkpoint.handle not in items and len(items) >= self.max_accounts:
            raise ValueError("X checkpoint account limit exceeded")
        items[checkpoint.handle] = checkpoint
        self._write(items)
        self._items = items

    def snapshot(self) -> tuple[XCheckpoint, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists() and self.path.is_file():
            self.path.chmod(0o600)

    def _read(self) -> dict[str, XCheckpoint]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError as exc:
            raise CheckpointFormatError("invalid X checkpoint JSON") from exc
        except OSError as exc:
            raise CheckpointFormatError("cannot read X checkpoint JSON") from exc
        if not isinstance(raw, dict) or set(raw) != _ROOT_FIELDS:
            raise CheckpointFormatError("invalid X checkpoint root schema")
        if raw.get("schema") != CHECKPOINT_SCHEMA:
            raise CheckpointFormatError("unsupported X checkpoint schema")
        accounts = raw.get("accounts")
        if not isinstance(accounts, dict) or len(accounts) > self.max_accounts:
            raise CheckpointFormatError("invalid X checkpoint accounts")
        output: dict[str, XCheckpoint] = {}
        for key, item in accounts.items():
            checkpoint = self._decode_account(key, item)
            if checkpoint.handle in output:
                raise CheckpointFormatError("duplicate normalized X checkpoint handle")
            output[checkpoint.handle] = checkpoint
        return output

    @staticmethod
    def _decode_account(key: object, item: object) -> XCheckpoint:
        if not isinstance(key, str) or not isinstance(item, dict):
            raise CheckpointFormatError("invalid X checkpoint account entry")
        if set(item) != _ACCOUNT_FIELDS:
            raise CheckpointFormatError("invalid X checkpoint account schema")
        if any(not isinstance(item[field], str) for field in _ACCOUNT_FIELDS):
            raise CheckpointFormatError("invalid X checkpoint account field types")
        try:
            checkpoint = XCheckpoint(
                item["handle"],
                item["user_id"],
                item["latest_tweet_id"],
            )
        except (TypeError, ValueError) as exc:
            raise CheckpointFormatError("invalid X checkpoint account values") from exc
        if key != checkpoint.handle:
            raise CheckpointFormatError("X checkpoint key does not match handle")
        return checkpoint

    def _write(self, items: dict[str, XCheckpoint]) -> None:
        self._secure_parent()
        accounts = {
            handle: {
                "handle": item.handle,
                "user_id": item.user_id,
                "latest_tweet_id": item.latest_tweet_id,
            }
            for handle, item in sorted(items.items())
        }
        document = json.dumps(
            {"schema": CHECKPOINT_SCHEMA, "accounts": accounts},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.path.parent,
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                temporary.chmod(0o600)
                stream.write(document + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()
