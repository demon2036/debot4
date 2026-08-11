from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from debot4.v6.grok.models import GrokSearchAnswer
from debot4.v6.narrative.research_package import ResearchMode
from debot4.v6.narrative.research_runtime import NarrativeResearchRuntime
from debot4.v6.narrative.research_store import NarrativeResearchStore
from debot4.v6.narrative.trusted_telegram import TelegramPostVerifier
from debot4.v6.telegram import TelegramPost, TelegramPostObservation


NOW = datetime(2026, 8, 10, 18, tzinfo=timezone.utc)


def _post() -> TelegramPost:
    return TelegramPost(
        "Yndegen",
        3749,
        "A fresh Solana meme narrative is spreading",
        NOW - timedelta(seconds=8),
        NOW - timedelta(seconds=2),
    )


class ExactTelegram:
    def __init__(self, post: TelegramPost) -> None:
        self.post = post
        self.calls: list[tuple[str, int]] = []

    def get_observation(
        self, channel: str, message_id: int
    ) -> TelegramPostObservation:
        self.calls.append((channel, message_id))
        return TelegramPostObservation(
            self.post,
            b"<html>exact-public-message</html>",
            "telegram:yndegen:3749:sha256",
        )


class Grok:
    def __init__(self) -> None:
        self.prompts: list[str] = []

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        assert instructions
        self.prompts.append(prompt)
        return GrokSearchAnswer(
            "grok-telegram-1",
            "grok-chat-fast",
            '{"narrative_key":"fresh-solana-meme",'
            '"one_line_meme":"Korean KOL propagation",'
            '"event_role":"amplification","why_now":"new public post",'
            '"unknowns":["exact CA not established"]}',
            (),
            (),
            (),
            {"total_tokens": 100},
        )

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        assert prompt and instructions
        return GrokSearchAnswer(
            "grok-telegram-format-1",
            "grok-chat-fast",
            '{"narrative_key":"fresh-solana-meme",'
            '"one_line_meme":"Korean KOL propagation",'
            '"event_role":"amplification","why_now":"new public post",'
            '"unknowns":["exact CA not established"]}',
            (),
            (),
            (),
            {"total_tokens": 50},
        )


class NoXLeads:
    def verify(self, _url: str) -> None:
        raise AssertionError("no X lead should be verified")


class EmptyXMonitor:
    def monitor_once(self):
        return ()


def test_telegram_runtime_verifies_exact_message_and_persists_research(
    tmp_path: Path,
) -> None:
    post = _post()
    source = ExactTelegram(post)
    grok = Grok()
    with NarrativeResearchStore(tmp_path / "research.sqlite3") as store:
        runtime = NarrativeResearchRuntime(
            monitor=EmptyXMonitor(),
            grok=grok,
            verifier=NoXLeads(),
            telegram_verifier=TelegramPostVerifier(fetcher=source),
            store=store,
            clock=lambda: NOW,
        )

        package = runtime.research_telegram_post(post)
        saved = store.get(package.package_id)

    assert package.mode is ResearchMode.ACTIVE_TELEGRAM
    assert package.status == "READY"
    assert source.calls == [("yndegen", 3749)]
    assert "telegram_channel_post" in grok.prompts[0]
    assert "已核验事件 URL: https://t.me/yndegen/3749" in grok.prompts[0]
    assert saved is not None
    assert saved["research_only"] is True
    assert saved["authorizes_trade"] is False
    assert saved["research"]["grok_answer_is_evidence"] is False
    assert saved["research"]["result"]["verified_urls"] == [
        "https://t.me/yndegen/3749"
    ]
    events = saved["research"]["result"]["events"]
    assert len(events) == 1
    assert events[0]["actor"]["handle"] == "yeonwoo1102"
    assert events[0]["exact_ca"] is False
