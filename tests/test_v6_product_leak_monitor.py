from datetime import datetime, timedelta, timezone

import pytest

from debot4.v6.explosion import ExplosionEventStore
from debot4.v6.product_leak import (
    JsonPublicResourceSnapshotStore,
    PublicResourceClient,
    PublicResourceError,
    PublicResourceMonitor,
    PublicResourceTarget,
)


NOW = datetime(2026, 8, 12, 18, 0, tzinfo=timezone.utc)
TARGET = PublicResourceTarget(
    "xai-bot-page", "x:spacexai", "official_company",
    "https://x.ai/bot", ("grok bot", "ai teammates"),
)


class Response:
    def __init__(
        self, url: str, body: bytes, content_type: str = "text/html; charset=utf-8",
    ) -> None:
        self.url = url
        self.body = body
        self.status = 200
        self.headers = {"content-type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def geturl(self):
        return self.url

    def read(self, size=-1):
        return self.body if size < 0 else self.body[:size]


class Opener:
    def __init__(self, responses: list[Response]) -> None:
        self.responses = responses

    def open(self, _request, *, timeout):
        assert timeout == 8.0
        return self.responses.pop(0)


def _client(*bodies: bytes) -> PublicResourceClient:
    return PublicResourceClient(
        opener=Opener([Response(TARGET.source_url, body) for body in bodies]),
        clock=iter((NOW, NOW + timedelta(seconds=2))).__next__,
    )


def test_client_extracts_terms_ca_title_and_public_artifacts() -> None:
    address = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"
    body = (
        f"<title>Grok Bot</title><a href='/bot/help'>AI teammates</a>{address}"
    ).encode()
    snapshot = _client(body).fetch(TARGET)

    assert snapshot.terms == frozenset({"grok bot", "ai teammates"})
    assert snapshot.token_addresses == frozenset({address.casefold()})
    assert snapshot.artifacts == frozenset({"https://x.ai/bot/help"})
    assert snapshot.title == "Grok Bot"


def test_client_extracts_title_from_text_mirror() -> None:
    snapshot = _client(b"Title: Grok Bot: A new kind of colleague\nGrok Bot").fetch(
        TARGET
    )

    assert snapshot.title == "Grok Bot: A new kind of colleague"


def test_client_fetches_mirror_but_keeps_canonical_evidence_url() -> None:
    target = PublicResourceTarget(
        "xai-bot-page", "x:spacexai", "official_company",
        "https://x.ai/bot", ("grok bot",),
        "https://r.jina.ai/https://x.ai/bot",
    )
    response = Response(target.fetch_url, b"Grok Bot", "text/plain")
    client = PublicResourceClient(opener=Opener([response]), clock=lambda: NOW)

    assert client.fetch(target).source_url == "https://x.ai/bot"


def test_monitor_baselines_then_emits_only_added_semantics(tmp_path) -> None:
    address = "0xabcdefabcdefabcdefabcdefabcdefabcdefabcd"
    client = _client(
        b"<title>Grok Bot</title>Grok Bot",
        f"<title>Grok Bot Beta</title>Grok Bot AI teammates {address}".encode(),
    )
    snapshots = JsonPublicResourceSnapshotStore(tmp_path / "resources.json")
    with ExplosionEventStore(tmp_path / "events.sqlite3") as events:
        monitor = PublicResourceMonitor(client, snapshots, events)
        assert monitor.poll(TARGET) == ()
        found = monitor.poll(TARGET)
        assert {item.subtype for item in found} == {
            "public_ca_added", "public_term_added", "public_title_changed",
        }
        assert events.count() == 3

    reloaded = JsonPublicResourceSnapshotStore(tmp_path / "resources.json")
    assert reloaded.load(TARGET.resource_id).token_addresses == frozenset({address})


def test_client_rejects_redirected_or_non_text_response() -> None:
    redirected = PublicResourceClient(
        opener=Opener([Response("https://evil.example/bot", b"Grok Bot")]),
        clock=lambda: NOW,
    )
    with pytest.raises(PublicResourceError, match="unexpected"):
        redirected.fetch(TARGET)

    binary = PublicResourceClient(
        opener=Opener([Response(TARGET.source_url, b"x", "image/png")]),
        clock=lambda: NOW,
    )
    with pytest.raises(PublicResourceError, match="content type"):
        binary.fetch(TARGET)
