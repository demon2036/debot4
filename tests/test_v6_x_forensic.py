from datetime import datetime, timezone

import pytest

from debot4.v6.x.forensic import (
    XForensicError,
    parse_forensic_profile,
    parse_forensic_timeline_page,
)


NOW = datetime(2026, 8, 13, 8, tzinfo=timezone.utc)
HANDLE = "BotOnBnb"
USER_ID = "108174884"


def _actor(handle: str = HANDLE, user_id: str = USER_ID) -> dict[str, object]:
    return {"screen_name": handle, "id": user_id}


def test_profile_exposes_resource_times_without_claiming_profile_action_time() -> None:
    profile = parse_forensic_profile(
        {
            "code": 200,
            "user": {
                **_actor(),
                "name": "$BOT",
                "description": "0xabc",
                "joined": "Mon Jan 25 03:00:15 +0000 2010",
                "avatar_url": (
                    "https://pbs.twimg.com/profile_images/"
                    "2086556924061892608/AaYn6P1V_normal.jpg"
                ),
                "banner_url": (
                    "https://pbs.twimg.com/profile_banners/108174884/1786308912"
                ),
                "verification": {"verified": True, "type": "individual"},
                "followers": 10,
                "tweets": 2,
            },
        },
        expected_handle="botonbnb",
        expected_user_id=USER_ID,
        fetched_at=NOW,
    )

    assert profile.avatar_resource_id == "2086556924061892608"
    assert profile.avatar_resource_at.isoformat() == "2026-08-09T20:55:11.706000+00:00"
    assert profile.banner_resource_at.isoformat() == "2026-08-09T20:55:12+00:00"
    assert profile.joined_at.year == 2010


def test_repost_keeps_original_time_but_marks_action_time_unavailable() -> None:
    row = {
        "type": "status",
        "id": "2086888845652467982",
        "text": "Bought some more $Xchange",
        "created_timestamp": 1_786_302_847,
        "author": _actor("BluntCap", "1576088736940658693"),
        "reposted_by": _actor(),
        "replying_to": None,
        "media": {},
    }
    page = parse_forensic_timeline_page(
        {"code": 200, "results": [row], "cursor": {"bottom": "next"}},
        expected_handle=HANDLE,
        expected_user_id=USER_ID,
        fetched_at=NOW,
    )

    action = page.actions[0]
    assert action.action_kind == "repost_snapshot"
    assert action.original_author == "bluntcap"
    assert action.timeline_actor == "botonbnb"
    assert action.exact_action_time_available is False
    assert page.bottom_cursor == "next"


def test_direct_media_only_post_and_stable_identity_are_preserved() -> None:
    row = {
        "type": "status",
        "id": "2085954475840127312",
        "text": "",
        "created_timestamp": 1_786_158_076,
        "author": _actor(),
        "reposted_by": None,
        "replying_to": None,
        "media": {"all": [{
            "id": "2085954469083197440",
            "url": "https://pbs.twimg.com/media/HPLMiatXsAAlQtW.png?name=orig",
        }]},
    }
    action = parse_forensic_timeline_page(
        {"code": 200, "results": [row]},
        expected_handle=HANDLE,
        expected_user_id=USER_ID,
        fetched_at=NOW,
    ).actions[0]

    assert action.action_kind == "post"
    assert action.text == "[media-only post]"
    assert action.exact_action_time_available is True
    assert action.media_ids == ("2085954469083197440",)


def test_profile_and_timeline_fail_closed_on_stable_id_substitution() -> None:
    with pytest.raises(XForensicError, match="identity mismatch"):
        parse_forensic_timeline_page(
            {"code": 200, "results": [{
                "type": "status",
                "id": "2085954475840127312",
                "text": "spoof",
                "created_timestamp": 1_786_158_076,
                "author": _actor(user_id="999999"),
                "reposted_by": None,
            }]},
            expected_handle=HANDLE,
            expected_user_id=USER_ID,
            fetched_at=NOW,
        )
