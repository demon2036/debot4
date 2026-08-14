import pytest

from debot4.v6.golden_dogs.wave_attribution import validate_wave_reviews


def review(**changes):
    row = {
        "label": "DOG", "wave_number": 1,
        "best_supported_driver": "previous_block_capital_first",
        "confidence": "medium",
        "narrative_source": "verified source",
        "official_or_avatar": "no eligible action",
        "advance_signal": "previous-block buy",
        "chain_ignition": "one verified buy",
        "propagation": "later social relay",
        "post_peak": "one recap",
        "counterevidence": ["correlation is not causation"],
        "unknowns": ["private order flow"],
    }
    row.update(changes)
    return row


def test_complete_review_ledger_is_accepted() -> None:
    assert validate_wave_reviews([review()], {("DOG", 1)}) == (("DOG", 1),)


@pytest.mark.parametrize("changes,match", [
    ({"confidence": "high"}, "confidence"),
    ({"best_supported_driver": "kol_caused_it"}, "driver"),
    ({"advance_signal": ""}, "advance_signal"),
    ({"unknowns": []}, "unknowns"),
])
def test_unreviewed_or_unsupported_claims_fail_closed(changes, match) -> None:
    with pytest.raises(ValueError, match=match):
        validate_wave_reviews([review(**changes)], {("DOG", 1)})


def test_duplicate_and_missing_waves_are_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_wave_reviews([review(), review()], {("DOG", 1)})
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_wave_reviews([review()], {("DOG", 1), ("DOG", 2)})
