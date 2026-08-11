"""Exact-block freshness boundary and final v6 entry authorization."""

from __future__ import annotations

from datetime import datetime
import re

from .domain import TokenRef
from .entry_models import (
    ENTRY_SCHEMA,
    EXECUTION_SCHEMA,
    EntryAuthorization,
    EntryStatus,
    ExecutionDecision,
    ExecutionPolicy,
    ExecutionStatus,
    HeadBoundary,
    QuoteBoundary,
)
from .gate_models import GateStatus, NarrativeGateDecision
from .hashing import canonical_sha256
from .models import aware_utc, is_exact_bsc_token


_HASH = re.compile(r"^0x[0-9a-f]{64}$")


def evaluate_execution_boundary(
    quote: QuoteBoundary,
    *,
    now: datetime,
    current_head: HeadBoundary | None,
    policy: ExecutionPolicy,
) -> ExecutionDecision:
    checked = aware_utc(now, "now")
    rejects = _quote_rejections(quote, checked, policy)
    quote_age = max(0.0, (checked - quote.completed_at).total_seconds())
    head_age: float | None = None
    lag: int | None = None
    waits: list[str] = []
    if quote_age > policy.max_quote_age_seconds:
        waits.append("quote_expired")
    if current_head is None:
        waits.append("current_head_unavailable")
    else:
        rejects.extend(_head_rejections(current_head, checked, policy))
        head_age = max(0.0, (checked - current_head.observed_at).total_seconds())
        lag = current_head.block_number - quote.block_number
        if current_head.observed_at < quote.completed_at:
            waits.append("head_predates_quote")
        if head_age > policy.max_head_age_seconds:
            waits.append("current_head_expired")
        if lag < 0:
            waits.append("current_head_behind_quote")
        elif lag > policy.max_head_lag_blocks:
            waits.append("quote_behind_current_head")
        elif lag == 0 and current_head.block_hash != quote.block_hash:
            waits.append("quote_reorged_at_current_height")
    status = (
        ExecutionStatus.REJECT if rejects
        else ExecutionStatus.REQUOTE if waits
        else ExecutionStatus.PASS
    )
    reasons = tuple(dict.fromkeys(rejects or waits or ["execution_boundary_passed"]))
    material = {
        "schema": EXECUTION_SCHEMA,
        "checked_at": checked.isoformat(),
        "quote": quote.to_payload(),
        "current_head": None if current_head is None else current_head.to_payload(),
        "policy": policy.to_payload(),
        "status": status.value,
        "reasons": list(reasons),
    }
    digest = canonical_sha256(material)
    return ExecutionDecision(
        status=status,
        reasons=reasons,
        checked_at=checked,
        identity=f"{EXECUTION_SCHEMA}:{digest}",
        identity_hash=digest,
        quote_age_seconds=quote_age,
        head_age_seconds=head_age,
        head_lag_blocks=lag,
    )


def authorize_entry(
    gate: NarrativeGateDecision,
    execution: ExecutionDecision,
) -> EntryAuthorization:
    rejects: list[str] = []
    waits: list[str] = []
    if gate.status is GateStatus.REJECT:
        rejects.extend(f"gate:{item}" for item in gate.reasons)
    elif gate.status is not GateStatus.PASS:
        waits.extend(f"gate:{item}" for item in gate.reasons)
    if execution.status is ExecutionStatus.REJECT:
        rejects.extend(f"execution:{item}" for item in execution.reasons)
    elif execution.status is not ExecutionStatus.PASS:
        waits.extend(f"execution:{item}" for item in execution.reasons)
    status = EntryStatus.REJECT if rejects else EntryStatus.WAIT if waits else EntryStatus.COMMIT
    reasons = tuple(dict.fromkeys(rejects or waits or ["v6_entry_authorized"]))
    material = {
        "schema": ENTRY_SCHEMA,
        "gate_identity": gate.identity,
        "gate_status": gate.status.value,
        "execution_identity": execution.identity,
        "execution_status": execution.status.value,
        "status": status.value,
        "reasons": list(reasons),
    }
    digest = canonical_sha256(material)
    return EntryAuthorization(
        status=status,
        reasons=reasons,
        identity=f"{ENTRY_SCHEMA}:{digest}",
        identity_hash=digest,
    )


def _quote_rejections(
    quote: QuoteBoundary,
    checked: datetime,
    policy: ExecutionPolicy,
) -> list[str]:
    reasons: list[str] = []
    try:
        token_valid = is_exact_bsc_token(TokenRef("bsc", quote.token_address))
    except (TypeError, ValueError):
        token_valid = False
    if not token_valid:
        reasons.append("invalid_quote_token")
    if not isinstance(quote.block_number, int) or isinstance(quote.block_number, bool) or quote.block_number < 0:
        reasons.append("invalid_quote_block_number")
    if not _HASH.fullmatch(quote.block_hash):
        reasons.append("invalid_quote_block_hash")
    if quote.block_timestamp > quote.completed_at:
        reasons.append("quote_time_order_invalid")
    if (quote.completed_at - checked).total_seconds() > policy.max_future_skew_seconds:
        reasons.append("quote_time_in_future")
    return reasons


def _head_rejections(
    head: HeadBoundary,
    checked: datetime,
    policy: ExecutionPolicy,
) -> list[str]:
    reasons: list[str] = []
    if not isinstance(head.block_number, int) or isinstance(head.block_number, bool) or head.block_number < 0:
        reasons.append("invalid_head_block_number")
    if not _HASH.fullmatch(head.block_hash):
        reasons.append("invalid_head_block_hash")
    if (head.observed_at - checked).total_seconds() > policy.max_future_skew_seconds:
        reasons.append("head_time_in_future")
    return reasons
