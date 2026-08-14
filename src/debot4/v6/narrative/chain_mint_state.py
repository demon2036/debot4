"""Small atomic cursor for restart-safe BSC mint block collection."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile


STATE_SCHEMA = "debot4.v6.chain-mint-checkpoint.v1"
_HASH = re.compile(r"0x[0-9a-f]{64}")


class ChainMintStateError(ValueError):
    """The local chain mint cursor is malformed."""


@dataclass(frozen=True, slots=True)
class ChainMintCheckpoint:
    block_number: int
    block_hash: str

    def __post_init__(self) -> None:
        block_hash = str(self.block_hash).strip().casefold()
        if (
            isinstance(self.block_number, bool) or self.block_number < 0
            or not _HASH.fullmatch(block_hash)
        ):
            raise ValueError("invalid chain mint checkpoint")
        object.__setattr__(self, "block_hash", block_hash)


class ChainMintCheckpointStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._secure_parent()
        self._checkpoint = self._read()

    def load(self) -> ChainMintCheckpoint | None:
        return self._checkpoint

    def save(self, checkpoint: ChainMintCheckpoint) -> None:
        document = json.dumps(
            {
                "schema": STATE_SCHEMA,
                "block_number": checkpoint.block_number,
                "block_hash": checkpoint.block_hash,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        self._secure_parent()
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
            self._checkpoint = checkpoint
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def _read(self) -> ChainMintCheckpoint | None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (OSError, json.JSONDecodeError) as exc:
            raise ChainMintStateError("invalid chain mint checkpoint JSON") from exc
        if (
            not isinstance(raw, dict)
            or set(raw) != {"schema", "block_number", "block_hash"}
            or raw.get("schema") != STATE_SCHEMA
        ):
            raise ChainMintStateError("unsupported chain mint checkpoint schema")
        try:
            return ChainMintCheckpoint(
                raw["block_number"], str(raw["block_hash"])
            )
        except (TypeError, ValueError) as exc:
            raise ChainMintStateError("invalid chain mint checkpoint values") from exc

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.is_symlink() or (self.path.exists() and not self.path.is_file()):
            raise ChainMintStateError("chain mint checkpoint must be a regular file")
        if self.path.is_file():
            self.path.chmod(0o600)
