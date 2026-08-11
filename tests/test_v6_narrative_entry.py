from __future__ import annotations

from datetime import datetime, timedelta, timezone

from debot4.v6.narrative import (
    EntryStatus,
    ExecutionPolicy,
    ExecutionStatus,
    GateStatus,
    HeadBoundary,
    NarrativeGateDecision,
    QuoteBoundary,
    Readiness,
    authorize_entry,
    evaluate_execution_boundary,
)
from debot4.v6.narrative.gate_models import CurrentWaveAssessment


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
TOKEN = "0x1111111111111111111111111111111111111111"
HASH_A = "0x" + "a" * 64
HASH_B = "0x" + "b" * 64
POLICY = ExecutionPolicy(2.0, 1.0, 1)


def _quote(**changes: object) -> QuoteBoundary:
    values = {
        "token_address": TOKEN,
        "block_number": 100,
        "block_hash": HASH_A,
        "block_timestamp": NOW - timedelta(seconds=1),
        "completed_at": NOW - timedelta(milliseconds=500),
    }
    values.update(changes)
    return QuoteBoundary(**values)


def _head(**changes: object) -> HeadBoundary:
    values = {
        "block_number": 100,
        "block_hash": HASH_A,
        "observed_at": NOW - timedelta(milliseconds=100),
    }
    values.update(changes)
    return HeadBoundary(**values)


def _gate(status: GateStatus) -> NarrativeGateDecision:
    reason = "gate_passed" if status is GateStatus.PASS else "gate_not_ready"
    return NarrativeGateDecision(
        status, NOW, (reason,), Readiness.PASS_TO_EXECUTION, "READY", True,
        CurrentWaveAssessment(GateStatus.PASS, ("fresh",)),
        f"gate:{status.value}", status.value.lower(), "dossier", "valuation",
    )


def test_v6_execution_boundary_passes_same_fresh_head() -> None:
    decision = evaluate_execution_boundary(
        _quote(), now=NOW, current_head=_head(), policy=POLICY
    )

    assert decision.status is ExecutionStatus.PASS
    assert decision.can_commit


def test_v6_execution_boundary_requotes_stale_or_reorged_quote() -> None:
    stale = evaluate_execution_boundary(
        _quote(
            block_timestamp=NOW - timedelta(seconds=4),
            completed_at=NOW - timedelta(seconds=3),
        ),
        now=NOW,
        current_head=_head(),
        policy=POLICY,
    )
    reorg = evaluate_execution_boundary(
        _quote(), now=NOW, current_head=_head(block_hash=HASH_B), policy=POLICY
    )

    assert stale.status is ExecutionStatus.REQUOTE
    assert "quote_expired" in stale.reasons
    assert reorg.status is ExecutionStatus.REQUOTE
    assert "quote_reorged_at_current_height" in reorg.reasons


def test_v6_missing_head_still_reports_expired_quote() -> None:
    decision = evaluate_execution_boundary(
        _quote(
            block_timestamp=NOW - timedelta(seconds=4),
            completed_at=NOW - timedelta(seconds=3),
        ),
        now=NOW,
        current_head=None,
        policy=POLICY,
    )

    assert decision.status is ExecutionStatus.REQUOTE
    assert "quote_expired" in decision.reasons
    assert "current_head_unavailable" in decision.reasons


def test_v6_invalid_quote_token_is_a_reject_not_an_exception() -> None:
    decision = evaluate_execution_boundary(
        _quote(token_address="not-an-address"),
        now=NOW,
        current_head=_head(),
        policy=POLICY,
    )

    assert decision.status is ExecutionStatus.REJECT
    assert "invalid_quote_token" in decision.reasons


def test_v6_entry_commits_only_when_gate_and_execution_both_pass() -> None:
    passed = evaluate_execution_boundary(
        _quote(), now=NOW, current_head=_head(), policy=POLICY
    )
    requote = evaluate_execution_boundary(
        _quote(), now=NOW, current_head=None, policy=POLICY
    )

    assert authorize_entry(_gate(GateStatus.PASS), passed).status is EntryStatus.COMMIT
    assert authorize_entry(_gate(GateStatus.WAIT), passed).status is EntryStatus.WAIT
    assert authorize_entry(_gate(GateStatus.PASS), requote).status is EntryStatus.WAIT
    assert authorize_entry(_gate(GateStatus.REJECT), passed).status is EntryStatus.REJECT
