"""Private restart-safe state for emitted market-anomaly stages."""

from __future__ import annotations

from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import re
import tempfile

from ..identity import utc_datetime


STATE_SCHEMA = "debot4.v6.market_anomaly_state.v1"
_ANOMALY_ID = re.compile(r"market-anomaly-[0-9a-f]{32}")


class MarketStateFormatError(ValueError):
    pass


class MarketAnomalyState:
    def __init__(
        self, path: str | Path, *, retention: timedelta = timedelta(days=3)
    ) -> None:
        if retention <= timedelta(0) or retention > timedelta(days=30):
            raise ValueError("market state retention must be in (0, 30 days]")
        self.path = Path(path)
        self.retention = retention
        self._secure_parent()
        self._emitted = self._read()

    def contains(self, anomaly_id: str) -> bool:
        return anomaly_id in self._emitted

    def mark(self, anomaly_ids: tuple[str, ...], emitted_at: datetime) -> None:
        stamp = utc_datetime(emitted_at)
        items = {
            key: value
            for key, value in self._emitted.items()
            if stamp - value <= self.retention
        }
        for anomaly_id in anomaly_ids:
            if not _ANOMALY_ID.fullmatch(anomaly_id):
                raise ValueError("invalid market anomaly identity")
            items[anomaly_id] = stamp
        self._write(items)
        self._emitted = items

    def snapshot(self) -> tuple[str, ...]:
        return tuple(sorted(self._emitted))

    def _secure_parent(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.path.parent.chmod(0o700)
        if self.path.is_file():
            self.path.chmod(0o600)

    def _read(self) -> dict[str, datetime]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise MarketStateFormatError("invalid market anomaly state") from exc
        if not isinstance(raw, dict) or set(raw) != {"schema", "emitted"}:
            raise MarketStateFormatError("invalid market anomaly state schema")
        emitted = raw.get("emitted")
        if raw.get("schema") != STATE_SCHEMA or not isinstance(emitted, dict):
            raise MarketStateFormatError("unsupported market anomaly state")
        if len(emitted) > 20_000:
            raise MarketStateFormatError("market anomaly state is too large")
        output: dict[str, datetime] = {}
        try:
            for key, value in emitted.items():
                if not isinstance(key, str) or not _ANOMALY_ID.fullmatch(key):
                    raise ValueError
                output[key] = utc_datetime(datetime.fromisoformat(str(value)))
        except (TypeError, ValueError) as exc:
            raise MarketStateFormatError("invalid market anomaly state entry") from exc
        return output

    def _write(self, items: dict[str, datetime]) -> None:
        self._secure_parent()
        document = json.dumps(
            {
                "schema": STATE_SCHEMA,
                "emitted": {
                    key: value.isoformat() for key, value in sorted(items.items())
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
