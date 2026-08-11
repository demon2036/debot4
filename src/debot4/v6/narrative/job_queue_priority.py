"""Transactional priority maintenance for queued narrative inputs."""

from __future__ import annotations

from collections.abc import Callable
import sqlite3

from .job_payloads import NarrativeJobInput
from .job_queue_models import job_from_row


def reprioritize_pending_rows(
    db: sqlite3.Connection,
    priority_for: Callable[[NarrativeJobInput], int],
    *,
    updated_at: str,
) -> int:
    """Reapply an injected application policy without owning that policy."""

    changed = 0
    rows = db.execute(
        "SELECT * FROM narrative_jobs WHERE status='pending'"
    ).fetchall()
    for row in rows:
        job = job_from_row(row)
        priority = priority_for(job.payload)
        if type(priority) is not int or not 1 <= priority <= 100:
            raise ValueError("priority policy must return an integer from 1 to 100")
        if priority != job.priority:
            changed += db.execute(
                "UPDATE narrative_jobs SET priority=?,updated_at=? "
                "WHERE job_id=? AND status='pending'",
                (priority, updated_at, job.job_id),
            ).rowcount
    return changed
