from datetime import datetime, timezone

import pytest

from debot4.v6.x import FxJsonDocument, XProfileClient, XProfileError


NOW = datetime(2026, 8, 10, 20, tzinfo=timezone.utc)


class FakeHttp:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.urls: list[str] = []

    def get_json(self, url: str) -> FxJsonDocument:
        self.urls.append(url)
        return FxJsonDocument(self.payload, NOW, 100)


def _payload(handle: str = "yeonwoo1102", user_id: str = "1444971805618302988"):
    return {
        "code": 200,
        "user": {
            "id": user_id,
            "screen_name": handle,
            "name": "Yeon",
            "description": "Korean degen",
        },
    }


def test_profile_client_preserves_stable_identity_and_bio() -> None:
    http = FakeHttp(_payload())

    profile = XProfileClient(http=http).fetch("@YeonWoo1102")

    assert profile.handle == "yeonwoo1102"
    assert profile.user_id == "1444971805618302988"
    assert profile.display_name == "Yeon"
    assert profile.description == "Korean degen"
    assert http.urls == ["https://api.fxtwitter.com/yeonwoo1102"]


def test_profile_client_rejects_handle_substitution() -> None:
    client = XProfileClient(http=FakeHttp(_payload(handle="imposter")))

    with pytest.raises(XProfileError, match="unexpected profile handle"):
        client.fetch("yeonwoo1102")
