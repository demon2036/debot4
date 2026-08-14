"""Run one bounded, read-only audit of the live mint-alert path."""

from __future__ import annotations

from datetime import timedelta
import json

from ..dex_audit.http import DirectJsonClient
from ..dex_audit.providers import fetch_bsc_gainers
from ..identity import utc_now
from .mint_alert_audit import audit_mint_alerts
from .mint_alert_audit_reader import read_debot_mints, read_mint_alerts
from .mint_alert_gate_codec import read_mint_alert_gate_state
from .settings import NarrativeSettings


def main() -> int:
    now = utc_now()
    try:
        settings = NarrativeSettings.from_env()
        gate = read_mint_alert_gate_state(settings.mint_alert_gate_path)
        if gate is None:
            raise RuntimeError("mint alert gate state is unavailable")
        since = max(gate.policy_started_at, now - timedelta(days=1))
        alerts = read_mint_alerts(settings.mint_alert_database, since=since)
        debot_mints = read_debot_mints(
            settings.mint_location_database, since=since
        )
        board = fetch_bsc_gainers(
            DirectJsonClient(
                timeout_seconds=settings.market_timeout_seconds,
                max_response_bytes=settings.max_response_bytes,
            ),
            as_of_us=int(now.timestamp() * 1_000_000),
            limit=100,
        )
        report = audit_mint_alerts(
            gate, alerts, debot_mints, board, now=now
        )
        print(json.dumps(
            report.as_public_dict(), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"),
        ), flush=True)
        return 1 if report.attention_required else 0
    except Exception as exc:
        print(json.dumps({
            "schema": "debot4.v6.mint-alert-audit.v1",
            "status": "error",
            "as_of": now.isoformat(),
            "error_type": type(exc).__name__,
            "error": str(exc)[:240],
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":")), flush=True)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
