"""Private restart-safe checkpoints for public Telegram channels."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile

from .models import TelegramCheckpoint, telegram_channel


CHECKPOINT_SCHEMA = "debot4.v6.telegram.checkpoints.v1"


class TelegramCheckpointFormatError(ValueError):
    """The persisted Telegram checkpoint document is invalid."""


class JsonTelegramCheckpointStore:
    def __init__(self, path: str | Path, *, max_channels: int = 256) -> None:
        if not 1 <= max_channels <= 10_000:
            raise ValueError("max_channels must be between 1 and 10000")
        self.path = Path(path)
        self.max_channels = max_channels
        self._secure_parent()
        self._items = self._read()

    def load(self, channel: str) -> TelegramCheckpoint | None:
        return self._items.get(telegram_channel(channel))

    def save(self, checkpoint: TelegramCheckpoint) -> None:
        items = dict(self._items)
        if checkpoint.channel not in items and len(items) >= self.max_channels:
            raise ValueError("Telegram checkpoint channel limit exceeded")
        items[checkpoint.channel] = checkpoint
        self._write(items)
        self._items = items

    def snapshot(self) -> tuple[TelegramCheckpoint, ...]:
        return tuple(self._items[key] for key in sorted(self._items))

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.exists() and self.path.is_file():
            self.path.chmod(0o600)

    def _read(self) -> dict[str, TelegramCheckpoint]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (json.JSONDecodeError, OSError) as exc:
            raise TelegramCheckpointFormatError(
                "cannot read Telegram checkpoint JSON"
            ) from exc
        if not isinstance(raw, dict) or set(raw) != {"schema", "channels"}:
            raise TelegramCheckpointFormatError("invalid Telegram checkpoint root")
        if raw.get("schema") != CHECKPOINT_SCHEMA:
            raise TelegramCheckpointFormatError("unsupported Telegram checkpoint schema")
        channels = raw.get("channels")
        if not isinstance(channels, dict) or len(channels) > self.max_channels:
            raise TelegramCheckpointFormatError("invalid Telegram channel map")
        output: dict[str, TelegramCheckpoint] = {}
        for key, value in channels.items():
            if not isinstance(key, str) or not isinstance(value, int):
                raise TelegramCheckpointFormatError("invalid Telegram checkpoint entry")
            try:
                checkpoint = TelegramCheckpoint(key, value)
            except ValueError as exc:
                raise TelegramCheckpointFormatError(
                    "invalid Telegram checkpoint value"
                ) from exc
            if key != checkpoint.channel or key in output:
                raise TelegramCheckpointFormatError("invalid Telegram checkpoint key")
            output[key] = checkpoint
        return output

    def _write(self, items: dict[str, TelegramCheckpoint]) -> None:
        self._secure_parent()
        document = json.dumps(
            {
                "schema": CHECKPOINT_SCHEMA,
                "channels": {
                    key: item.latest_message_id for key, item in sorted(items.items())
                },
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent,
                prefix=f".{self.path.name}.", suffix=".tmp", delete=False,
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
