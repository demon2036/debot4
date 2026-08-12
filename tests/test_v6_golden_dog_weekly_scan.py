from datetime import datetime, timezone

from debot4.v6.golden_dogs.weekly_scan import (
    consecutive_windows,
    prompt_sha256,
    sweep_prompts,
    window_for_timestamp,
)


UTC = timezone.utc


def test_one_year_is_partitioned_without_gaps_or_overlap() -> None:
    start = datetime(2025, 8, 12, tzinfo=UTC)
    end = datetime(2026, 8, 12, tzinfo=UTC)
    windows = consecutive_windows(start, end)
    assert len(windows) == 53
    assert windows[0].start == start
    assert windows[-1].end_exclusive == end
    assert all(left.end_exclusive == right.start for left, right in zip(windows, windows[1:]))
    assert all((item.end_exclusive - item.start).days <= 7 for item in windows)


def test_each_window_has_three_distinct_evidence_first_sweeps() -> None:
    window = consecutive_windows(
        datetime(2025, 8, 12, tzinfo=UTC),
        datetime(2025, 8, 19, tzinfo=UTC),
    )[0]
    prompts = sweep_prompts(window)
    assert len(prompts) == 3
    assert len({prompt_sha256(item) for item in prompts}) == 3
    assert all("500,000" in item and "exact 0x contract" in item for item in prompts)
    assert all("DeBot or GMGN" in item for item in prompts)


def test_timestamp_maps_to_one_half_open_window() -> None:
    windows = consecutive_windows(
        datetime(2025, 8, 12, tzinfo=UTC),
        datetime(2025, 8, 26, tzinfo=UTC),
    )
    boundary = int(windows[0].end_exclusive.timestamp())
    assert window_for_timestamp(windows, boundary) == windows[1]
    assert window_for_timestamp(windows, boundary - 1) == windows[0]
