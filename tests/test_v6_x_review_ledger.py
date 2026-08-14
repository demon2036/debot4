import pytest

from debot4.v6.golden_dogs.x_post_semantics import XPostSemantic
from debot4.v6.golden_dogs.x_review_ledger import (
    XPostOrigin,
    validate_and_join_x_reviews,
)


def evidence(tweet_id="1", address="0xabc"):
    return {
        "tweet_id": tweet_id, "address": address, "label": "DOG",
        "author_handle": "caller", "published_at": "2026-08-06T00:00:00Z",
        "status_url": "https://x.com/caller/status/1",
        "status_payload_sha256": "a" * 64, "text_sha256": "b" * 64,
    }


def review(tweet_id="1", address="0xABC", **changes):
    row = {
        "tweet_id": tweet_id, "address": address,
        "semantic": "market_thesis", "origin": "independent",
        "reason": "directional thesis with literal CA",
    }
    row.update(changes)
    return row


def test_exact_coverage_joins_receipts_and_enums() -> None:
    rows = validate_and_join_x_reviews([evidence()], [review()])
    assert len(rows) == 1
    assert rows[0].semantic is XPostSemantic.MARKET_THESIS
    assert rows[0].origin is XPostOrigin.INDEPENDENT
    assert rows[0].status_payload_sha256 == "a" * 64


def test_missing_or_extra_review_is_rejected() -> None:
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_and_join_x_reviews([evidence()], [])
    with pytest.raises(ValueError, match="coverage mismatch"):
        validate_and_join_x_reviews([], [review()])


def test_duplicate_association_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate review association"):
        validate_and_join_x_reviews([evidence()], [review(), review()])


@pytest.mark.parametrize("field,value", [
    ("semantic", "bullish"), ("origin", "kol"),
])
def test_unknown_review_enum_is_rejected(field, value) -> None:
    with pytest.raises(ValueError, match="invalid review enum"):
        validate_and_join_x_reviews(
            [evidence()], [review(**{field: value})],
        )


def test_empty_reason_is_rejected() -> None:
    with pytest.raises(ValueError, match="review reason is required"):
        validate_and_join_x_reviews([evidence()], [review(reason="")])
