from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal

from debot4.v6.domain import DeBotSignal
from debot4.v6.grok import GrokCitation, GrokSearchAnswer, GrokSearchSource
from debot4.v6.narrative.passive_trigger import (
    PassiveNarrativeStatus,
    PassiveNarrativeTrigger,
    investigate_passive_signal,
)
from debot4.v6.narrative import (
    FxTwitterObservation,
    FxTwitterTweet,
    XStatusVerifier,
)


UTC = timezone.utc
TOKEN = "0xABCDEFabcdefABCDEFabcdefABCDEFabcdefABCD"
STATUS = "1890071433214038103"


class FakeGrok:
    def __init__(self, response: GrokSearchAnswer | Exception) -> None:
        self.response = response
        self.calls: list[tuple[str, str]] = []
        self.format_calls: list[tuple[str, str]] = []

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        self.calls.append((prompt, instructions))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        self.format_calls.append((prompt, instructions))
        assert not isinstance(self.response, Exception)
        return self.response


class FakeFetcher:
    def fetch_observation(self, status_url: str) -> FxTwitterObservation:
        assert status_url == f"https://x.com/cz_binance/status/{STATUS}"
        tweet = FxTwitterTweet(
            STATUS,
            "cz_binance",
            "902926941413453824",
            "Broccoli story and current catalyst",
            datetime(2026, 8, 9, 9, 58, tzinfo=UTC),
            datetime(2026, 8, 9, 10, 0, 3, tzinfo=UTC),
            status_url,
        )
        return FxTwitterObservation(tweet, b"verified-passive-status", "cf-ray:test")


def _verifier() -> XStatusVerifier:
    return XStatusVerifier(fetcher=FakeFetcher())


def _signal() -> DeBotSignal:
    return DeBotSignal(
        signal_id="signal-42",
        token_address=TOKEN,
        signal_kind="kol",
        group_name="KOL#1min#3",
        event_at=datetime(2026, 8, 9, 10, 0, tzinfo=UTC),
        available_at=datetime(2026, 8, 9, 10, 0, 2, tzinfo=UTC),
        channel_id="2",
        pair_address=None,
        dex_name="PancakeSwap",
        token_name="  Meme North Star  ",
        token_symbol=" MNS ",
        token_decimals=18,
        total_supply=Decimal("1000000000"),
        created_at=None,
        provider_fdv_usd=Decimal("125000"),
        provider_liquidity_usd=Decimal("22000"),
        narrative_urls=(
            "https://x.com/project/status/1890071433214038000",
            "javascript:alert(1)",
        ),
        description="provider profile text",
        wallet_trades=(),
        kol_buy_qualified=True,
        kol_buy_reason="provider_ui_buy_with_windowed_wallet_trades",
    )


def _answer(
    *,
    sources: tuple[GrokSearchSource, ...] = (),
    citations: tuple[GrokCitation, ...] = (),
    candidates: tuple[str, ...] = (),
) -> GrokSearchAnswer:
    return GrokSearchAnswer(
        "grok-response-7",
        "grok-chat-fast",
        '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
        '"event_role":"catalyst","why_now":"new CZ post","unknowns":["CA"]}',
        sources,
        citations,
        candidates,
        {},
    )


def test_normal_search_returns_only_source_backed_exact_x_status_leads() -> None:
    supported = f"https://x.com/cz_binance/status/{STATUS}"
    text_only = "https://x.com/rumor/status/1890071433214038999"
    answer = _answer(
        sources=(
            GrokSearchSource(supported, "CZ", "x"),
            GrokSearchSource("https://example.com/context", "context", "web"),
        ),
        citations=(GrokCitation(supported, "CZ citation"),),
        candidates=(supported, text_only),
    )
    client = FakeGrok(answer)

    result = investigate_passive_signal(_signal(), client, _verifier())

    assert result.status is PassiveNarrativeStatus.WAIT
    assert result.answer is answer
    assert [lead.status_id for lead in result.x_status_leads] == [STATUS]
    assert result.reason == "verified_narrative_found_trigger_ca_unbound"
    assert result.events == ()
    assert result.authorizes_trade is False
    assert result.trigger.exact_ca == TOKEN.lower()
    assert result.trigger.signal_id == "signal-42"
    assert result.trigger.observed_at == datetime(2026, 8, 9, 10, 0, 2, tzinfo=UTC)
    assert result.trigger.token_name == "Meme North Star"
    assert result.trigger.token_symbol == "MNS"
    assert result.trigger.social_urls == (
        "https://x.com/project/status/1890071433214038000",
    )
    prompt, instructions = client.calls[0]
    assert TOKEN.lower() in prompt
    assert "Meme North Star" in prompt
    assert "signal-42" in prompt
    assert result.trigger.social_urls[0] in prompt
    assert "从异动时间向前搜索" in prompt
    assert "禁止补写链接" in instructions
    payload = result.to_payload()
    assert payload["authorizes_trade"] is False
    assert payload["contains_verified_events"] is False


def test_answer_without_source_or_citation_is_wait_even_with_text_url() -> None:
    answer = _answer(
        candidates=(f"https://x.com/cz_binance/status/{STATUS}",)
    )

    result = investigate_passive_signal(_signal(), FakeGrok(answer), _verifier())

    assert result.status is PassiveNarrativeStatus.WAIT
    assert result.reason == "no_verified_narrative_evidence"
    assert result.answer is answer
    assert result.x_status_leads == ()
    assert result.authorizes_trade is False


def test_trigger_status_is_verified_before_search_and_added_to_context() -> None:
    status_url = f"https://x.com/cz_binance/status/{STATUS}"
    signal = replace(_signal(), narrative_urls=(status_url,))
    client = FakeGrok(_answer())

    result = investigate_passive_signal(signal, client, _verifier())

    assert result.reason == "verified_narrative_found_trigger_ca_unbound"
    assert result.verified_urls == (status_url,)
    assert "FxTwitter 已即时核验的触发原帖" in client.calls[0][0]
    assert "Broccoli story and current catalyst" in client.calls[0][0]
    assert client.format_calls


def test_grok_exception_fails_closed_without_leaking_or_creating_candidates() -> None:
    client = FakeGrok(RuntimeError("upstream secret failure"))

    result = investigate_passive_signal(
        _signal(), client, _verifier(),
        anomaly="price and volume accelerated in one minute"
    )

    assert result.status is PassiveNarrativeStatus.WAIT
    assert result.reason == "grok_search_failed"
    assert "secret" not in result.reason
    assert result.answer is None
    assert result.x_status_leads == ()
    assert result.authorizes_trade is False
    assert result.trigger.anomaly == "price and volume accelerated in one minute"


def test_trigger_identity_is_deterministic_and_payload_keeps_audit_fields() -> None:
    first = PassiveNarrativeTrigger.from_signal(_signal())
    second = PassiveNarrativeTrigger.from_signal(_signal())

    assert first.trigger_id == second.trigger_id
    assert first.to_payload() == second.to_payload()
    assert first.to_payload()["social_urls_are_evidence"] is False
