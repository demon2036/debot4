"""Finite public-resource baseline; no scheduler, model, or trading path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..product_leak import (
    BOT_PUBLIC_RESOURCES,
    JsonPublicResourceSnapshotStore,
    PublicResourceClient,
    PublicResourceMonitor,
    PublicResourceTarget,
)
from .store import ExplosionEventStore


@dataclass(frozen=True, slots=True)
class ProductTargetResult:
    resource_id: str
    source_url: str
    events: int
    error_type: str = ""

    @property
    def ok(self) -> bool:
        return not self.error_type

    def as_dict(self) -> dict[str, object]:
        return {
            "resource_id": self.resource_id,
            "source_url": self.source_url,
            "events": self.events,
            "ok": self.ok,
            "error_type": self.error_type,
        }


def sample_product_baseline(
    *,
    state_dir: str | Path,
) -> dict[str, object]:
    root = Path(state_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    results: list[ProductTargetResult] = []
    event_count = 0
    with ExplosionEventStore(root / "explosion-events.sqlite3") as events:
        monitor = PublicResourceMonitor(
            PublicResourceClient(),
            JsonPublicResourceSnapshotStore(root / "public-resources.json"),
            events,
        )
        for target in BOT_PUBLIC_RESOURCES:
            results.append(_sample_target(monitor, target))
        event_count = events.count()
    return {
        "mode": "one_shot_public_resource_baseline",
        "collectors_started": False,
        "grok_triggered": False,
        "trading_started": False,
        "targets": [item.as_dict() for item in results],
        "event_count": event_count,
        "transport": {
            "strategy": "direct_https_with_reviewed_mirror_targets",
            "x_egress_pool_used": False,
        },
    }


def _sample_target(
    monitor: PublicResourceMonitor,
    target: PublicResourceTarget,
) -> ProductTargetResult:
    try:
        return ProductTargetResult(
            target.resource_id, target.source_url, len(monitor.poll(target)),
        )
    except (RuntimeError, ValueError) as exc:
        return ProductTargetResult(
            target.resource_id, target.source_url, 0, type(exc).__name__,
        )
