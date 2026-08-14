"""Orchestrate exact X-to-DeBot alert and market-coverage audits."""

from __future__ import annotations

from datetime import datetime

from ..dex_audit.models import Board
from ..identity import utc_datetime
from .market_signal import MarketAnomaly, MarketQualityPolicy
from .mint_alert_audit_models import (
    DeBotMintSeen,
    MarketCoverageRow,
    MintAlertAuditReport,
    StoredMintAlert,
)
from .mint_alert_audit_rules import alert_violations
from .mint_alert_gate_codec import MintAlertGateGroup, MintAlertGateState
from .mint_market_scope import scope_recent_mint_candidates


EXACT_MARKET_SOURCE = "coinmarketcap_datahub"


def audit_mint_alerts(
    gate: MintAlertGateState,
    alerts: tuple[StoredMintAlert, ...],
    debot_mints: tuple[DeBotMintSeen, ...],
    board: Board,
    *,
    now: datetime,
    policy: MarketQualityPolicy | None = None,
    debot_exact_ca_count: int | None = None,
) -> MintAlertAuditReport:
    """Audit alert invariants and classify exact current market leads."""

    current = utc_datetime(now)
    market_available = (
        board.source == EXACT_MARKET_SOURCE and board.ranking_exact and board.success
    )
    selection = (policy or MarketQualityPolicy()).select(board)
    scope = scope_recent_mint_candidates(
        selection.anomalies if market_available else (),
        board.rows,
        now=current,
        policy_started_at=gate.policy_started_at,
    )
    leads = _market_coverage(
        scope.eligible, gate, alerts, debot_mints
    )
    return MintAlertAuditReport(
        as_of=current,
        policy_started_at=gate.policy_started_at,
        gate_groups=len(gate.groups),
        alerts=len(alerts),
        debot_exact_cas=(
            len(debot_mints)
            if debot_exact_ca_count is None
            else debot_exact_ca_count
        ),
        market_source=board.source,
        market_available=market_available,
        market_failure_reason=_market_failure(board, market_available),
        market_scope=scope,
        violations=alert_violations(gate, alerts, current),
        market_leads=leads,
    )


def _market_coverage(
    anomalies: tuple[MarketAnomaly, ...],
    gate: MintAlertGateState,
    alerts: tuple[StoredMintAlert, ...],
    debot_mints: tuple[DeBotMintSeen, ...],
) -> tuple[MarketCoverageRow, ...]:
    alert_by_ca = {
        item.alert.exact_ca: item
        for item in alerts
        if item.alert.raised_at >= gate.policy_started_at
    }
    debot_by_ca = {item.exact_ca: item for item in debot_mints}
    groups_by_ca: dict[str, MintAlertGateGroup] = {}
    for group in sorted(gate.groups, key=lambda item: item.updated_at):
        for match in group.matches:
            groups_by_ca[match.exact_ca] = group
    rows = []
    for anomaly in anomalies:
        alert = alert_by_ca.get(anomaly.exact_ca)
        seen = debot_by_ca.get(anomaly.exact_ca)
        group = groups_by_ca.get(anomaly.exact_ca)
        coverage = (
            "alerted"
            if alert is not None
            else "debot_seen_unalerted"
            if seen is not None
            else "not_seen_by_debot"
        )
        rows.append(MarketCoverageRow(
            anomaly=anomaly,
            coverage=coverage,
            debot=seen,
            gate_outcome=None if group is None else group.outcome,
            gate_reason=None if group is None else group.reason,
            alert=alert,
        ))
    return tuple(rows)


def _market_failure(board: Board, available: bool) -> str | None:
    if available:
        return None
    if board.failure_reason:
        return board.failure_reason
    if board.source != EXACT_MARKET_SOURCE:
        return f"exact market board unavailable; received {board.source}"
    if not board.ranking_exact:
        return "market board ranking is not exact"
    return "exact market board returned no rows"


__all__ = ["EXACT_MARKET_SOURCE", "audit_mint_alerts"]
