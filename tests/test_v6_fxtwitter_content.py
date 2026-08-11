from datetime import datetime, timezone

from debot4.v6.narrative.fxtwitter import parse_fxtwitter_payload


NOW = datetime(2026, 8, 11, 8, tzinfo=timezone.utc)
STATUS_ID = "2086934705207959965"


def _payload(**tweet_fields: object) -> dict[str, object]:
    return {
        "code": 200,
        "tweet": {
            "id": STATUS_ID,
            "text": "",
            "created_timestamp": NOW.timestamp() - 10,
            "author": {
                "screen_name": "JensenHuang",
                "id": "2070631956824698880",
            },
            **tweet_fields,
        },
    }


def test_status_article_is_preserved_as_verifiable_content() -> None:
    tweet = parse_fxtwitter_payload(
        _payload(article={
            "title": "NVIDIA AI Factory Compute Is Becoming an Investable Asset Class",
            "preview_text": "AI factory compute can be financed and deployed.",
            "description": "A long-form X article.",
        }),
        expected_id=STATUS_ID,
        fetched_at=NOW,
    )

    assert tweet.text == (
        "[article]\n"
        "NVIDIA AI Factory Compute Is Becoming an Investable Asset Class\n"
        "AI factory compute can be financed and deployed.\n"
        "A long-form X article."
    )
    assert tweet.author_id == "2070631956824698880"


def test_plain_status_text_remains_authoritative() -> None:
    tweet = parse_fxtwitter_payload(
        _payload(text="Compute is becoming investable."),
        expected_id=STATUS_ID,
        fetched_at=NOW,
    )

    assert tweet.text == "Compute is becoming investable."
