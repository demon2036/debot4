from __future__ import annotations

from datetime import datetime, timezone

from debot4.v6.x import (
    FxJsonDocument,
    FxTwitterRepostMonitor,
    XRepostTarget,
)


FIRST = datetime(2026, 8, 11, 12, 0, tzinfo=timezone.utc)
SECOND = datetime(2026, 8, 11, 12, 0, 1, tzinfo=timezone.utc)
USER_ID = "1873269053265182720"


class FakeHttp:
    def __init__(self, documents: list[FxJsonDocument]) -> None:
        self.documents = documents
        self.urls: list[str] = []

    def get_json(self, url: str) -> FxJsonDocument:
        self.urls.append(url)
        return self.documents.pop(0)


def _identity(handle: str, actor_id: str) -> dict[str, str]:
    return {"screen_name": handle, "id": actor_id}


def _repost(tweet_id: str, *, reposter_id: str = USER_ID) -> dict[str, object]:
    return {
        "type": "status",
        "id": tweet_id,
        "text": f"original {tweet_id}",
        "created_timestamp": 1_786_000_000,
        "author": _identity("elonmusk", "44196397"),
        "reposted_by": _identity("jtitordemon2036", reposter_id),
    }


def _document(rows: list[dict[str, object]], stamp: datetime) -> FxJsonDocument:
    return FxJsonDocument({"code": 200, "results": rows}, stamp, 100)


def test_baseline_then_detects_repost_of_an_older_original_tweet() -> None:
    baseline_id = "2087000000000000000"
    older_new_repost_id = "1987000000000000000"
    http = FakeHttp([
        _document([_repost(baseline_id)], FIRST),
        _document(
            [_repost(older_new_repost_id), _repost(baseline_id)], SECOND
        ),
    ])
    ticks = iter((0.0, 1.0))
    monitor = FxTwitterRepostMonitor(
        (XRepostTarget("jtitordemon2036", USER_ID),),
        http=http,
        clock=lambda: next(ticks),
    )

    assert monitor.poll_once() == ()
    found = monitor.poll_once()

    assert len(found) == 1
    assert found[0].original_tweet_id == older_new_repost_id
    assert found[0].detected_at == SECOND
    assert found[0].canonical_url == (
        f"https://x.com/elonmusk/status/{older_new_repost_id}"
    )
    snapshot = monitor.snapshot()
    assert snapshot["initialized_targets"] == 1
    assert snapshot["total_events"] == 1
    assert snapshot["likes_supported"] is False
    assert snapshot["exact_action_time_available"] is False
    assert snapshot["enters_narrative_queue"] is False
    assert snapshot["recent_events"][0]["detected_at"] == SECOND.isoformat()


def test_wrong_stable_reposter_identity_fails_closed() -> None:
    http = FakeHttp([
        _document([_repost("2087000000000000000", reposter_id="999999")], FIRST)
    ])
    monitor = FxTwitterRepostMonitor(
        (XRepostTarget("jtitordemon2036", USER_ID),),
        http=http,
        clock=lambda: 0.0,
    )

    assert monitor.poll_once() == ()

    snapshot = monitor.snapshot()
    assert snapshot["initialized_targets"] == 0
    assert snapshot["total_events"] == 0
    assert snapshot["last_error_types"] == {
        "jtitordemon2036": "XRepostError"
    }


def test_poll_interval_prevents_duplicate_requests_and_events() -> None:
    http = FakeHttp([_document([_repost("2087000000000000000")], FIRST)])
    ticks = iter((0.0, 0.5))
    monitor = FxTwitterRepostMonitor(
        (XRepostTarget("jtitordemon2036", USER_ID),),
        http=http,
        clock=lambda: next(ticks),
    )

    assert monitor.poll_once() == ()
    assert monitor.poll_once() == ()
    assert len(http.urls) == 1
