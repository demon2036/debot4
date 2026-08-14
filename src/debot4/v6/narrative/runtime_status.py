"""Live, credential-free overlay for the dashboard status snapshot."""

from __future__ import annotations

from typing import Any

from .app import NarrativeApp
from .status import status_snapshot


def app_status_snapshot(app: NarrativeApp) -> dict[str, Any]:
    snapshot = status_snapshot(app.settings)
    service = app.service
    if service is None:
        snapshot["runtime"] = {"running": False, "research_configured": False}
        return snapshot
    realtime = (
        None
        if app.telegram_realtime is None
        else app.telegram_realtime.snapshot().as_public_dict()
    )
    reposts = (
        None
        if app.x_repost_monitor is None
        else app.x_repost_monitor.snapshot()
    )
    snapshot["runtime"] = {
        "running": True,
        "research_configured": True,
        "source_error_types": dict(service.last_source_error_types),
        "collector_error_type": service.last_collector_error_type,
        "worker_error_type": service.last_worker_error_type,
        "worker_error_types": dict(service.last_worker_error_types),
        "research_workers": len(service.workers),
        "signal_filter": app.collector.filter_snapshot(),
        "telegram_realtime_error_type": service.last_realtime_error_type,
        "telegram_realtime": realtime,
        "x_reposts": reposts,
        "x_last_polled_targets": app.monitor.last_polled_targets,
        "x_last_failures": len(app.monitor.last_failures),
        "telegram_last_polled_targets": app.telegram_monitor.last_polled_targets,
        "telegram_last_failures": len(app.telegram_monitor.last_failures),
        "market_last_error_type": app.market_monitor.last_error_type,
        "market_last_rejections": dict(
            app.market_monitor.last_rejection_counts
        ),
    }
    snapshot["egress"] = (
        {"available": False, "configured_nodes": 0}
        if app.x_egress_pool is None
        else app.x_egress_pool.snapshot()
    )
    return snapshot
