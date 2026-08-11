"""One bounded first-start replay rule shared by social monitors."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timezone
import math
from typing import TypeVar


T = TypeVar("T")


def bounded_initial_replay(
    items: Iterable[T], *, limit: int, key: Callable[[T], int],
    eligible: Callable[[T], bool] | None = None,
) -> tuple[tuple[T, ...], int]:
    """Return only the newest initial items and the number intentionally skipped."""

    if isinstance(limit, bool) or not 1 <= limit <= 20:
        raise ValueError("initial replay limit must be between 1 and 20")
    ordered = tuple(sorted(items, key=key))
    candidates = ordered if eligible is None else tuple(filter(eligible, ordered))
    selected = candidates[-limit:]
    return selected, len(ordered) - len(selected)


def inside_initial_window(
    created_at: datetime,
    observed_at: datetime,
    *,
    max_age_seconds: float,
    future_skew_seconds: float = 30.0,
) -> bool:
    """Accept only genuinely recent first-start items, with bounded clock skew."""

    if not math.isfinite(max_age_seconds) or not 1 <= max_age_seconds <= 3_600:
        raise ValueError("initial replay age must be between 1 and 3600 seconds")
    if created_at.tzinfo is None or observed_at.tzinfo is None:
        raise ValueError("initial replay timestamps must be timezone-aware")
    age = (
        observed_at.astimezone(timezone.utc)
        - created_at.astimezone(timezone.utc)
    ).total_seconds()
    return -future_skew_seconds <= age <= max_age_seconds
