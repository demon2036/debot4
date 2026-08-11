from datetime import datetime, timezone
import os

import pytest

from debot4.v6.narrative.actor_registry import (
    ActorRegistry,
    DEFAULT_ACTOR_REGISTRY,
)
from debot4.v6.narrative.telegram_monitor import TelegramNarrativeMonitor
from debot4.v6.telegram import (
    JsonTelegramCheckpointStore,
    TelegramChannelBatch,
    TelegramCheckpoint,
    TelegramPost,
    TelegramPublicClient,
    TelegramUnavailable,
)
from debot4.v6.telegram.http import TelegramHtmlDocument
from debot4.v6.telegram.parser import parse_telegram_page


NOW = datetime(2026, 8, 10, 17, 30, tzinfo=timezone.utc)


def _message_html(channel: str = "Yndegen", message_id: int = 3749) -> str:
    return f"""
    <div class="tgme_channel_info">channel</div>
    <section class="tgme_channel_history">
      <div class="tgme_widget_message js-widget_message" data-post="{channel}/{message_id}">
        <a class="tgme_widget_message_reply" href="https://t.me/other/9">
          <div class="js-message_reply_text">quoted text must not leak</div>
        </a>
        <div class="tgme_widget_message_text js-message_text">
          Main &amp; exact<br/>0x1111111111111111111111111111111111111111
          <a href="https://x.com/example/status/1">source</a>
        </div>
        <a class="tgme_widget_message_photo_wrap"></a>
        <time datetime="2026-08-10T16:49:26+00:00"></time>
      </div>
    </section>
    """


def test_parser_extracts_author_text_exact_url_time_and_contract() -> None:
    page = parse_telegram_page(_message_html(), "Yndegen", NOW)

    assert page.is_public_channel
    assert len(page.posts) == 1
    post = page.posts[0]
    assert post.channel == "yndegen"
    assert post.message_id == 3749
    assert "quoted text" not in post.text
    assert post.text.startswith("Main & exact")
    assert post.has_media
    assert post.bsc_contracts == (
        "0x1111111111111111111111111111111111111111",
    )
    assert "https://x.com/example/status/1" in post.urls
    assert post.canonical_url == "https://t.me/yndegen/3749"


class _Html:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.urls: list[str] = []

    def get_html(self, url: str) -> TelegramHtmlDocument:
        self.urls.append(url)
        return TelegramHtmlDocument(self.pages[url], NOW, len(self.pages[url]))


def test_client_distinguishes_public_empty_contact_and_exact_message() -> None:
    listing = "<div class='tgme_channel_info'></div><div>No posts found</div>"
    contact = "<div class='tgme_page_title'>Contact</div>"
    exact_url = "https://t.me/yndegen/3749?embed=1&mode=tme"
    http = _Html({
        "https://t.me/s/pote_korea": listing,
        "https://t.me/s/d11111d1": contact,
        exact_url: _message_html(),
    })
    client = TelegramPublicClient(http)

    empty = client.poll("pote_korea")
    assert empty.posts == ()
    assert empty.checkpoint == TelegramCheckpoint("pote_korea", 0)
    with pytest.raises(TelegramUnavailable):
        client.poll("D11111D1")
    assert client.get_message("Yndegen", 3749).message_id == 3749


def test_checkpoint_store_is_private_atomic_and_rejects_corruption(tmp_path) -> None:
    path = tmp_path / "private" / "telegram.json"
    store = JsonTelegramCheckpointStore(path)
    store.save(TelegramCheckpoint("Yndegen", 3749))

    assert store.load("@YNDEGEN") == TelegramCheckpoint("yndegen", 3749)
    assert os.stat(path).st_mode & 0o777 == 0o600
    assert os.stat(path.parent).st_mode & 0o777 == 0o700
    assert JsonTelegramCheckpointStore(path).snapshot() == (
        TelegramCheckpoint("yndegen", 3749),
    )


class _Poller:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    def poll(
        self, channel: str, checkpoint: TelegramCheckpoint | None = None,
    ) -> TelegramChannelBatch:
        previous = checkpoint.latest_message_id if checkpoint else 0
        self.calls.append((channel, previous))
        post = TelegramPost(channel, previous + 1, "new", NOW, NOW)
        return TelegramChannelBatch(
            (post,), TelegramCheckpoint(channel, previous + 1), 1
        )


def test_monitor_polls_reviewed_channels_and_advances_only_after_accept(tmp_path) -> None:
    clock = [0.0]
    poller = _Poller()
    monitor = TelegramNarrativeMonitor(
        tmp_path / "telegram.json", client=poller, clock=lambda: clock[0],
        wall_clock=lambda: NOW,
    )

    def reject(_posts: tuple[TelegramPost, ...]) -> None:
        raise RuntimeError("durable queue unavailable")

    assert monitor.monitor_once(reject) == ()
    assert len(monitor.last_failures) == len(monitor.targets)
    assert monitor.checkpoints.snapshot() == ()

    clock[0] = 20.0
    accepted: list[TelegramPost] = []
    fresh = monitor.monitor_once(lambda posts: accepted.extend(posts))
    expected = {item.channel for item in monitor.targets}
    assert len(fresh) == len(accepted) == len(expected)
    assert {item.channel for item in accepted} == expected
    assert len(monitor.checkpoints.snapshot()) == len(expected)


def test_first_telegram_poll_keeps_only_latest_message(tmp_path) -> None:
    class ReplayPoller:
        def __init__(self) -> None:
            self.calls = 0

        def poll(self, channel, checkpoint=None) -> TelegramChannelBatch:
            self.calls += 1
            ids = (10, 11, 12) if self.calls == 1 else (12, 13)
            posts = tuple(
                TelegramPost(channel, item, f"message {item}", NOW, NOW)
                for item in ids
            )
            return TelegramChannelBatch(
                posts, TelegramCheckpoint(channel, max(ids)), len(posts)
            )

    registration = next(
        item for item in DEFAULT_ACTOR_REGISTRY.registrations()
        if item.actor.handle == "yeonwoo1102"
    )
    clock = [0.0]
    monitor = TelegramNarrativeMonitor(
        tmp_path / "telegram.json",
        client=ReplayPoller(),
        registry=ActorRegistry((registration,)),
        clock=lambda: clock[0],
        wall_clock=lambda: NOW,
    )

    first = monitor.monitor_once()
    assert tuple(item.message_id for item in first) == (12,)
    assert monitor.last_initial_replay_dropped == 2
    assert monitor.checkpoints.load("yndegen") == TelegramCheckpoint("yndegen", 12)
    clock[0] = 20.0
    assert tuple(item.message_id for item in monitor.monitor_once()) == (13,)
