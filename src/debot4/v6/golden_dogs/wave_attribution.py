"""Pure validation rules for the manually reviewed wave attribution ledger."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


CONFIDENCE_LEVELS = frozenset({"medium_high", "medium", "medium_low", "low"})
DRIVER_CLASSES = frozenset({
    "same_block_capital_first",
    "previous_block_capital_first",
    "capital_then_social_amplification",
    "fresh_public_thesis_and_market_flow",
    "project_operations_and_market_flow",
    "standing_narrative_and_market_flow",
    "unresolved_market_repricing",
})
TEXT_FIELDS = (
    "narrative_source",
    "official_or_avatar",
    "advance_signal",
    "chain_ignition",
    "propagation",
    "post_peak",
)
LIST_FIELDS = ("counterevidence", "unknowns")


def wave_key(row: Mapping[str, object]) -> tuple[str, int]:
    """Return the stable project/wave identity used across all evidence ledgers."""

    label = row.get("label")
    number = row.get("wave_number")
    if not isinstance(label, str) or not label.strip():
        raise ValueError("wave review requires a non-empty label")
    if not isinstance(number, int) or isinstance(number, bool) or number < 1:
        raise ValueError(f"{label}: wave_number must be a positive integer")
    return label, number


def validate_wave_reviews(
    rows: Iterable[Mapping[str, object]],
    expected_keys: Iterable[tuple[str, int]],
) -> tuple[tuple[str, int], ...]:
    """Fail closed on missing, duplicated, unreviewed, or invalid wave judgments."""

    expected = set(expected_keys)
    seen: set[tuple[str, int]] = set()
    for row in rows:
        key = wave_key(row)
        if key in seen:
            raise ValueError(f"duplicate wave review: {key}")
        seen.add(key)
        if row.get("best_supported_driver") not in DRIVER_CLASSES:
            raise ValueError(f"{key}: invalid best_supported_driver")
        if row.get("confidence") not in CONFIDENCE_LEVELS:
            raise ValueError(f"{key}: invalid confidence")
        for field in TEXT_FIELDS:
            value = row.get(field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{key}: {field} must be reviewed")
        for field in LIST_FIELDS:
            value = row.get(field)
            if not isinstance(value, list) or not value or not all(
                isinstance(item, str) and item.strip() for item in value
            ):
                raise ValueError(f"{key}: {field} must be a non-empty string list")
    missing, extra = expected - seen, seen - expected
    if missing or extra:
        raise ValueError(f"wave review coverage mismatch: missing={missing}, extra={extra}")
    return tuple(sorted(seen))
