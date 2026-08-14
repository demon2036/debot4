import json
from datetime import datetime, timezone

from debot4.v6.golden_dogs.x_task_scope import (
    expected_authors_by_status_id,
    scope_verified_status,
)


UTC = timezone.utc
START = datetime(2025, 8, 12, tzinfo=UTC)
END = datetime(2026, 8, 13, tzinfo=UTC)


def _row(**overrides):
    row = {
        "status": "verified",
        "canonical_url": "https://x.com/new_handle/status/123456",
        "observed_author_id": "42",
        "published_at": "2026-01-02T03:04:05Z",
    }
    row.update(overrides)
    return row


def test_expected_authors_are_bound_to_successful_task_stable_ids() -> None:
    lines = (
        json.dumps({
            "status": "success", "answer": "ok", "stable_user_id": "42",
            "candidate_urls": ["https://x.com/old_handle/status/123456"],
        }),
        json.dumps({
            "status": "error", "stable_user_id": "99",
            "candidate_urls": ["https://x.com/other/status/123456"],
        }),
    )

    assert expected_authors_by_status_id(lines) == {"123456": frozenset({"42"})}


def test_scope_accepts_handle_change_when_stable_id_time_and_status_id_match() -> None:
    verdict, allowed = scope_verified_status(
        _row(), expected_authors={"123456": frozenset({"42"})},
        window_start=START, window_end_exclusive=END,
    )

    assert verdict == "accepted"
    assert allowed == ("42",)


def test_scope_rejects_model_cross_account_leak_and_out_of_window_post() -> None:
    mismatch, _ = scope_verified_status(
        _row(observed_author_id="99"),
        expected_authors={"123456": frozenset({"42"})},
        window_start=START, window_end_exclusive=END,
    )
    outside, _ = scope_verified_status(
        _row(published_at="2025-08-11T23:59:59Z"),
        expected_authors={"123456": frozenset({"42"})},
        window_start=START, window_end_exclusive=END,
    )

    assert mismatch == "task_author_mismatch"
    assert outside == "outside_scan_window"


def test_scope_preserves_direct_x_unavailable_as_a_distinct_gap() -> None:
    verdict, allowed = scope_verified_status(
        _row(status="status_unavailable"),
        expected_authors={"123456": frozenset({"42"})},
        window_start=START, window_end_exclusive=END,
    )

    assert verdict == "direct_x_unavailable"
    assert allowed == ()
