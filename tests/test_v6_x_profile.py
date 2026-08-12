from datetime import datetime, timezone

import pytest

from debot4.v6.x import FxJsonDocument, XCheckpoint, XProfileClient, XProfileError


NOW = datetime(2026, 8, 10, 20, tzinfo=timezone.utc)


class FakeHttp:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get_json(self, url: str) -> FxJsonDocument:
        self.urls.append(url)
        return FxJsonDocument(self.payload, NOW, 100, "0" * 64, "cf-ray:test")


def _payload(handle: str = "yeonwoo1102", user_id: str = "1444971805618302988"):
    return {
        "code": 200,
        "user": {
            "id": user_id,
            "screen_name": handle,
            "name": "Yeon",
            "description": "Korean degen",
            "avatar_url": "https://pbs.twimg.com/profile_images/1/avatar.jpg",
            "banner_url": "https://pbs.twimg.com/profile_banners/1/2",
            "url": "https://x.com/yeonwoo1102",
            "website": {"url": "https://example.com", "display_url": "example.com"},
            "verification": {"verified": True, "type": "blue"},
            "followers": 123,
            "following": 45,
            "statuses": 67,
            "media_count": 8,
            "likes": 9,
            "about_account": {
                "based_in": "South Korea",
                "username_changes": {
                    "count": 2,
                    "last_changed_at": "2026-08-01T00:00:00Z",
                },
            },
        },
    }


def test_profile_client_preserves_stable_identity_and_bio() -> None:
    http = FakeHttp(_payload())

    profile = XProfileClient(http=http).fetch("@YeonWoo1102")

    assert profile.handle == "yeonwoo1102"
    assert profile.user_id == "1444971805618302988"
    assert profile.display_name == "Yeon"
    assert profile.description == "Korean degen"
    assert profile.avatar_url.endswith("/avatar.jpg")
    assert profile.verified is True
    assert profile.followers == 123
    assert profile.based_in == "South Korea"
    assert profile.username_change_count == 2
    assert http.urls == [
        "https://api.fxtwitter.com/2/profile/yeonwoo1102?about_account=1"
    ]


def test_profile_observation_keeps_provider_receipt() -> None:
    evidence = XProfileClient(http=FakeHttp(_payload())).fetch_observation(
        "yeonwoo1102",
    )

    assert evidence.profile.user_id == "1444971805618302988"
    assert evidence.source_url == (
        "https://api.fxtwitter.com/2/profile/yeonwoo1102?about_account=1"
    )
    assert evidence.sha256 == "0" * 64
    assert evidence.response_identity == "cf-ray:test"
    assert evidence.following_count_verified is True


def test_profile_client_rejects_handle_substitution() -> None:
    client = XProfileClient(http=FakeHttp(_payload(handle="imposter")))

    with pytest.raises(XProfileError, match="unexpected profile handle"):
        client.fetch("yeonwoo1102")


def test_json_document_can_retain_raw_response_fingerprint() -> None:
    document = FxJsonDocument(_payload(), NOW, 100, "0" * 64, "cf-ray:test")

    assert document.sha256 == "0" * 64
    assert document.response_identity == "cf-ray:test"


def test_legacy_short_x_user_ids_are_valid_but_short_post_ids_are_not() -> None:
    assert XCheckpoint("pud", "107").user_id == "107"
    with pytest.raises(ValueError, match="latest_tweet_id"):
        XCheckpoint("pud", "107", "107")
