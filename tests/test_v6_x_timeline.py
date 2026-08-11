from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping
from urllib.parse import parse_qs, urlsplit

import pytest

from debot4.v6.x import FxJsonDocument, XCheckpoint, XTimelineClient
from debot4.v6.x.timeline import XTimelineError


NOW = datetime(2026, 8, 10, 16, tzinfo=timezone.utc)


class FakeHttp:
    def __init__(self, documents: list[FxJsonDocument | None]) -> None:
        self.documents = documents
        self.urls: list[str] = []

    def get_json(self, url: str) -> FxJsonDocument | None:
        self.urls.append(url)
        return self.documents.pop(0)


def _document(results: list[dict[str, object]]) -> FxJsonDocument:
    return FxJsonDocument({"code": 200, "results": results}, NOW, 100)


def _actor(handle: str = "cz_binance", actor_id: str = "902926941413453824"):
    return {"screen_name": handle, "id": actor_id}


def _status(tweet_id: str, text: str, **extra: object) -> dict[str, object]:
    return {
        "type": "status",
        "id": tweet_id,
        "text": text,
        "created_timestamp": NOW.timestamp() - 10,
        "author": _actor(),
        "replying_to": None,
        "reposted_by": None,
        **extra,
    }


def test_initial_poll_emits_recent_posts_and_establishes_identity() -> None:
    http = FakeHttp([_document([_status("2086840000000000001", "Broccoli")])])
    client = XTimelineClient(http=http, initial_lookback_seconds=60, clock=lambda: NOW)

    batch = client.poll("@CZ_Binance")

    assert [post.text for post in batch.posts] == ["Broccoli"]
    assert batch.posts[0].canonical_url == (
        "https://x.com/cz_binance/status/2086840000000000001"
    )
    assert batch.checkpoint.user_id == "902926941413453824"
    query = parse_qs(urlsplit(http.urls[0]).query)
    assert int(query["since"][0]) == int(NOW.timestamp()) - 60


def test_checkpoint_emits_only_newer_posts_and_uses_incremental_since() -> None:
    old_id = "2086840000000000001"
    new_id = "2086840000000000002"
    http = FakeHttp([_document([_status(old_id, "old"), _status(new_id, "new")])])
    client = XTimelineClient(http=http, clock=lambda: NOW)

    batch = client.poll(
        "cz_binance", XCheckpoint("cz_binance", "902926941413453824", old_id)
    )

    assert [post.tweet_id for post in batch.posts] == [new_id]
    assert int(parse_qs(urlsplit(http.urls[0]).query)["since"][0]) > 0


def test_reply_quote_and_contract_are_preserved_but_reposts_are_not_forged() -> None:
    contract = "0x1111111111111111111111111111111111111111"
    rows = [
        _status(
            "2086840000000000003", f"look {contract}",
            replying_to={"screen_name": "heyibinance"},
        ),
        _status(
            "2086840000000000004", "quoted",
            quote={"text": "origin", "author": _actor("elonmusk", "44196397")},
        ),
        _status(
            "2086840000000000005", "original content",
            author=_actor("theunipcs", "1755899659040555009"),
            reposted_by=_actor(),
        ),
    ]
    batch = XTimelineClient(http=FakeHttp([_document(rows)]), clock=lambda: NOW).poll(
        "cz_binance", XCheckpoint("cz_binance", "902926941413453824")
    )

    assert [post.post_type for post in batch.posts] == ["reply", "quote"]
    assert batch.posts[0].target_author == "heyibinance"
    assert batch.posts[0].bsc_contracts == (contract,)
    assert batch.posts[1].target_author == "elonmusk"
    assert batch.posts[1].target_text == "origin"


def test_non_text_article_media_and_quote_posts_are_preserved_without_endorsement() -> None:
    rows = [
        _status(
            "2086840000000000007", "",
            article={"title": "Builder call", "preview_text": "Weekly recap"},
        ),
        _status(
            "2086840000000000008", "",
            media={"photos": [{"url": "https://pbs.twimg.com/photo.jpg"}]},
            raw_text={"facets": [{
                "replacement": "https://x.com/cz_binance/status/2086840000000000008/photo/1"
            }]},
        ),
        _status(
            "2086840000000000009", "",
            quote={"text": "origin claim", "author": _actor("elonmusk", "44196397")},
        ),
    ]

    batch = XTimelineClient(http=FakeHttp([_document(rows)]), clock=lambda: NOW).poll(
        "cz_binance", XCheckpoint("cz_binance", "902926941413453824")
    )

    assert [post.text for post in batch.posts] == [
        "[article]\nBuilder call\nWeekly recap",
        "[media-only post]",
        "[quote-only post]",
    ]
    assert batch.posts[1].urls == (
        "https://x.com/cz_binance/status/2086840000000000008/photo/1",
    )
    assert batch.posts[2].post_type == "quote"
    assert batch.posts[2].target_text == "origin claim"


def test_identity_mismatch_fails_closed_and_204_keeps_seeded_checkpoint() -> None:
    wrong = _status("2086840000000000006", "spoof", author=_actor("cz_binance", "999999"))
    client = XTimelineClient(http=FakeHttp([_document([wrong])]), clock=lambda: NOW)
    state = XCheckpoint("cz_binance", "902926941413453824", "2086840000000000001")

    with pytest.raises(XTimelineError, match="identity"):
        client.poll("cz_binance", state)

    empty = XTimelineClient(http=FakeHttp([None]), clock=lambda: NOW).poll(
        "cz_binance", state
    )
    assert empty.posts == ()
    assert empty.checkpoint == state
