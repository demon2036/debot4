"""Pure consistency rules for durable mint-alert state."""

from __future__ import annotations

from datetime import datetime, timedelta

from .mint_alert import MINT_ALERT_SLA_SECONDS
from .mint_alert_audit_models import AuditViolation, StoredMintAlert
from .mint_alert_gate_codec import MintAlertGateGroup, MintAlertGateState
from .mint_alert_policy import MintAlertAction


MISSING_ALERT_GRACE_SECONDS = 5.0
RECENT_ORPHAN_WINDOW = timedelta(hours=1)


def alert_violations(
    gate: MintAlertGateState,
    alerts: tuple[StoredMintAlert, ...],
    now: datetime,
) -> tuple[AuditViolation, ...]:
    valid = tuple(item for item in alerts if item.alert.raised_at >= gate.policy_started_at)
    by_match = {item.alert.match.match_id: item for item in valid}
    selected: set[str] = set()
    output: list[AuditViolation] = []
    for group in gate.groups:
        match_ids = {item.match_id for item in group.matches}
        linked = tuple(by_match[key] for key in match_ids if key in by_match)
        if group.outcome == MintAlertAction.ALERT.value:
            selected_id = group.selected_match_id
            if selected_id is not None:
                selected.add(selected_id)
                match = next(item for item in group.matches if item.match_id == selected_id)
                if (
                    selected_id not in by_match
                    and now >= match.observed_at
                    + timedelta(seconds=MISSING_ALERT_GRACE_SECONDS)
                ):
                    output.append(_violation(
                        "selected_alert_missing",
                        group.tweet_id,
                        "gate selected a match but the durable alert row is absent",
                    ))
        elif group.outcome == MintAlertAction.REJECT.value and linked:
            output.append(_violation(
                "rejected_group_has_alert",
                group.tweet_id,
                "a rejected tweet group still has a durable alert",
            ))
        if group.reason == "post_alert_multiple_exact_cas":
            output.append(_violation(
                "post_alert_multiple_exact_cas",
                group.tweet_id,
                "a second exact CA appeared after an alert decision",
            ))
        if group.outcome == "pending" and _group_age(group, now) > MINT_ALERT_SLA_SECONDS:
            output.append(_violation(
                "pending_group_deadline_elapsed",
                group.tweet_id,
                "a pending candidate remained unresolved after the alert SLA",
            ))
    orphan_cutoff = max(gate.policy_started_at, now - RECENT_ORPHAN_WINDOW)
    for stored in valid:
        alert = stored.alert
        if alert.raised_at >= orphan_cutoff and alert.match.match_id not in selected:
            output.append(_violation(
                "alert_not_selected_by_gate",
                alert.alert_id,
                "a recent alert is not selected by retained gate state",
            ))
        if alert.detection_latency_seconds > MINT_ALERT_SLA_SECONDS:
            output.append(_violation(
                "detection_sla_missed",
                alert.alert_id,
                f"raised after {alert.detection_latency_seconds:.3f}s",
            ))
        delivery = stored.delivered_at
        if delivery is None:
            if (now - alert.match.catalyst_created_at).total_seconds() > MINT_ALERT_SLA_SECONDS:
                output.append(_violation(
                    "delivery_pending_past_sla",
                    alert.alert_id,
                    "alert remains undelivered after the SLA",
                ))
        else:
            latency = (delivery - alert.match.catalyst_created_at).total_seconds()
            if latency > MINT_ALERT_SLA_SECONDS:
                output.append(_violation(
                    "delivery_sla_missed",
                    alert.alert_id,
                    f"delivered after {latency:.3f}s",
                ))
    return tuple(sorted(output, key=lambda item: (item.code, item.subject)))


def _group_age(group: MintAlertGateGroup, now: datetime) -> float:
    created = min(item.catalyst_created_at for item in group.matches)
    return (now - created).total_seconds()


def _violation(code: str, subject: str, detail: str) -> AuditViolation:
    return AuditViolation(code, subject, detail)


__all__ = ["alert_violations"]
