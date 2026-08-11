from datetime import datetime, timedelta, timezone

from debot4.v6.grok import GrokApiError, GrokSearchAnswer
from debot4.v6.narrative import (
    ActorCapability,
    ActorRef,
    ActorRegistration,
    ActorRegistry,
    ActorTier,
    FxTwitterObservation,
    FxTwitterTweet,
    NarrativeEventKind,
    XStatusVerifier,
)
from debot4.v6.narrative.active_trigger import (
    ActiveNarrativeTrigger,
    ActiveTriggerStatus,
    investigate_active_trigger,
)
from debot4.v6.x import XPost


UTC = timezone.utc
NOW = datetime(2026, 8, 9, 12, tzinfo=UTC)
STATUS_ID = "1890071433214038103"
AUTHOR_ID = "902926941413453824"
URL = f"https://x.com/cz_binance/status/{STATUS_ID}"
TEXT = "Broccoli's Story: meet my dog Broccoli."


class FakeFetcher:
    def fetch_observation(self, status_url: str) -> FxTwitterObservation:
        assert status_url == URL
        tweet = FxTwitterTweet(
            STATUS_ID,
            "cz_binance",
            AUTHOR_ID,
            TEXT,
            NOW - timedelta(minutes=1),
            NOW,
            URL,
        )
        return FxTwitterObservation(tweet, b"verified-provider-body", "cf-ray:test")


class FakeGrok:
    def __init__(self, answer: GrokSearchAnswer | Exception) -> None:
        self.answer = answer
        self.last_prompt = ""

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        self.last_prompt = prompt
        assert "Broccoli" in prompt
        assert "取证" in instructions
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer:
        assert prompt and instructions
        assert not isinstance(self.answer, Exception)
        return self.answer


def _verifier() -> XStatusVerifier:
    actor = ActorRef(
        "x:cz_binance",
        "cz_binance",
        ActorTier.ECOSYSTEM_AUTHORITY,
        "test reviewed",
        ("bsc",),
        (
            ActorCapability.ESTABLISH_ORIGIN,
            ActorCapability.CREATE_CATALYST,
        ),
    )
    registry = ActorRegistry((ActorRegistration(
        actor,
        ("https://x.com/cz_binance/status/",),
        (AUTHOR_ID,),
    ),))
    return XStatusVerifier(FakeFetcher(), registry)


def _trigger(text: str = TEXT) -> ActiveNarrativeTrigger:
    return ActiveNarrativeTrigger.from_post(XPost(
        STATUS_ID,
        "cz_binance",
        text,
        NOW - timedelta(minutes=1),
        NOW,
    ))


def _answer(text: str, *urls: str) -> GrokSearchAnswer:
    return GrokSearchAnswer(
        "grok-1", "grok-chat-fast", text, (), (), urls, {}
    )


def test_verified_active_post_produces_source_and_catalyst_package() -> None:
    answer = _answer(
        '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
        '"event_role":"source","why_now":"new CZ post","unknowns":["no CA"]}',
        URL,
    )

    grok = FakeGrok(answer)
    result = investigate_active_trigger(_trigger(), grok=grok, verifier=_verifier())

    assert result.status is ActiveTriggerStatus.READY
    assert result.authorizes_trade is False
    assert {item.kind for item in result.events} == {
        NarrativeEventKind.SOURCE_EVENT,
        NarrativeEventKind.CURRENT_CATALYST,
    }
    assert '"tier":"ecosystem_authority"' in grok.last_prompt
    assert '"create_catalyst"' in grok.last_prompt
    assert "事件类型: post" in grok.last_prompt
    assert f"已核验事件 URL: {URL}" in grok.last_prompt


def test_quote_context_is_search_input_but_must_be_independently_verified() -> None:
    answer = _answer(
        '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
        '"event_role":"source","why_now":"new","unknowns":[]}',
        URL,
    )
    post = XPost(
        STATUS_ID, "cz_binance", TEXT, NOW - timedelta(minutes=1), NOW,
        "quote", "elonmusk", "original target text",
    )
    grok = FakeGrok(answer)

    investigate_active_trigger(
        ActiveNarrativeTrigger.from_post(post), grok=grok, verifier=_verifier()
    )

    assert "事件类型: quote" in grok.last_prompt
    assert "被回复/引用账号: elonmusk" in grok.last_prompt
    assert "独立核验回复/引用对象" in grok.last_prompt


def test_grok_failure_or_missing_status_url_waits() -> None:
    failed = investigate_active_trigger(
        _trigger(),
        grok=FakeGrok(GrokApiError("offline")),
        verifier=_verifier(),
    )
    no_url = investigate_active_trigger(
        _trigger(),
        grok=FakeGrok(_answer(
            '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
            '"event_role":"source","why_now":"new","unknowns":[]}'
        )),
        verifier=_verifier(),
    )

    assert failed.status is ActiveTriggerStatus.WAIT
    assert no_url.reason == "grok_returned_no_verifiable_x_status"


def test_monitor_and_provider_content_must_match() -> None:
    answer = _answer("{}", URL)

    result = investigate_active_trigger(
        _trigger("tampered monitor text"),
        grok=FakeGrok(answer),
        verifier=_verifier(),
    )

    assert result.reason == "trigger_content_mismatch"
