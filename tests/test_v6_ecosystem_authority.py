from datetime import datetime, timedelta, timezone

import pytest

from debot4.v6.ecosystem_authority import (
    AuthorityNode,
    BOT_AUTHORITY_NODES,
    FollowingClient,
    FollowingError,
    FollowingSnapshot,
    following_change_events,
)
from debot4.v6.x import FxJsonDocument


NOW = datetime(2026, 8, 12, 18, tzinfo=timezone.utc)
BOT = AuthorityNode(
    "bot", "2085838061347217408", "Grok Bot", "official_product",
    "https://x.com/bot",
)


def test_bot_network_includes_x_as_authority_not_kol() -> None:
    x = next(node for node in BOT_AUTHORITY_NODES if node.handle == "x")

    assert x.user_id == "783214"
    assert x.role == "official_platform"
    assert all("kol" not in node.role for node in BOT_AUTHORITY_NODES)


class FakeHttp:
    def __init__(self, pages: dict[str, object]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def get_json(self, url: str) -> FxJsonDocument:
        self.urls.append(url)
        payload = self.pages[url]
        return FxJsonDocument(payload, NOW, 100, f"{len(self.urls):064x}")


def _page(rows: list[tuple[str, str]], bottom: str) -> dict[str, object]:
    return {
        "code": 200,
        "results": [
            {"id": user_id, "screen_name": handle, "name": handle}
            for user_id, handle in rows
        ],
        "cursor": {"top": "-1|test", "bottom": bottom},
    }


def test_following_client_requires_complete_cursor_pagination() -> None:
    base = "https://api.fxtwitter.com/2/profile/bot/following"
    cursor = "123|456"
    http = FakeHttp({
        base: _page([("44196397", "elonmusk")], cursor),
        f"{base}?cursor=123%7C456": _page(
            [("34743251", "SpaceX")], "0|done",
        ),
    })

    snapshot = FollowingClient(http=http).fetch(BOT)

    assert snapshot.following == {
        "44196397": "elonmusk", "34743251": "spacex",
    }
    assert snapshot.page_count == 2
    assert len(snapshot.evidence_hash) == 64
    assert len(http.urls) == 2


def test_following_client_rejects_truncated_pagination() -> None:
    base = "https://api.fxtwitter.com/2/profile/bot/following"
    http = FakeHttp({base: _page([("44196397", "elonmusk")], "123|456")})

    with pytest.raises(FollowingError, match="exceeded"):
        FollowingClient(http=http, max_pages=1).fetch(BOT)


def test_following_diff_emits_added_and_removed_without_fake_action_time() -> None:
    previous = FollowingSnapshot.create(
        actor=BOT,
        observed_at=NOW - timedelta(seconds=2),
        source_url="https://api.fxtwitter.com/2/profile/bot/following",
        page_hashes=("a" * 64,),
        following={"44196397": "elonmusk", "34743251": "spacex"},
    )
    current = FollowingSnapshot.create(
        actor=BOT,
        observed_at=NOW,
        source_url="https://api.fxtwitter.com/2/profile/bot/following",
        page_hashes=("b" * 64,),
        following={"44196397": "elonmusk", "1720665183188922368": "grok"},
    )

    events = following_change_events(previous, current)
    by_type = {event.subtype: event for event in events}

    assert by_type["authority_follow_added"].subject == "@bot -> @grok"
    assert by_type["authority_follow_removed"].subject == "@bot -> @spacex"
    assert all(event.occurred_at == NOW for event in events)
    assert all(event.buy_eligible is False for event in events)
