from __future__ import annotations

from debot4.v6.grok.models import GrokSearchAnswer
from debot4.v6.grok.structured import search_narrative_brief


VALID = (
    '{"narrative_key":"Broccoli","one_line_meme":"CZ dog story",'
    '"event_role":"source","why_now":"new post","unknowns":[]}'
)


def _answer(response_id: str, text: str) -> GrokSearchAnswer:
    return GrokSearchAnswer(
        response_id, "grok-chat-fast", text, (), (), (), {}
    )


class TwoStageGrok:
    def __init__(
        self,
        search: GrokSearchAnswer | Exception,
        formatted: GrokSearchAnswer | Exception,
    ) -> None:
        self.search_response = search
        self.format_response = formatted
        self.x_calls: list[tuple[str, str]] = []
        self.format_calls: list[tuple[str, str]] = []

    def search_x(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        self.x_calls.append((prompt, instructions))
        if isinstance(self.search_response, Exception):
            raise self.search_response
        return self.search_response

    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        raise AssertionError("native X search should be preferred")

    def format_json(self, prompt: str, *, instructions: str) -> GrokSearchAnswer:
        self.format_calls.append((prompt, instructions))
        if isinstance(self.format_response, Exception):
            raise self.format_response
        return self.format_response


def test_native_x_search_is_always_followed_by_non_search_formatting() -> None:
    search = _answer("search", "Broccoli evidence with direct URLs")
    formatted = _answer("format", VALID)
    grok = TwoStageGrok(search, formatted)

    result = search_narrative_brief(grok, "find it", instructions="search")

    assert result.ok is True
    assert result.answer is search
    assert result.repair_answer is formatted
    assert result.brief is not None
    assert result.brief.narrative_key == "Broccoli"
    assert len(grok.x_calls) == 1
    assert len(grok.format_calls) == 1
    assert "不得新增" in grok.format_calls[0][0]
    assert "严格 JSON 格式化器" in grok.format_calls[0][1]


def test_search_failure_stops_before_formatting() -> None:
    grok = TwoStageGrok(
        RuntimeError("secret upstream detail"), _answer("x", VALID)
    )

    result = search_narrative_brief(grok, "find it", instructions="search")

    assert result.ok is False
    assert result.error == "grok_search_failed"
    assert result.answer is None
    assert grok.format_calls == []
    assert "secret" not in result.error


def test_format_failure_preserves_search_answer_and_waits() -> None:
    search = _answer("search", "verified evidence")
    result = search_narrative_brief(
        TwoStageGrok(search, RuntimeError("offline")),
        "find it",
        instructions="search",
    )

    assert result.ok is False
    assert result.error == "grok_format_failed"
    assert result.answer is search
    assert result.repair_answer is None


def test_invalid_formatted_json_retains_both_answers() -> None:
    search = _answer("search", "verified evidence")
    formatted = _answer("format", "broken json")
    result = search_narrative_brief(
        TwoStageGrok(search, formatted), "find it", instructions="search"
    )

    assert result.ok is False
    assert result.error == "grok_brief_invalid"
    assert result.answer is search
    assert result.repair_answer is formatted


def test_semantic_schema_echo_is_hard_rejected() -> None:
    echoed = _answer(
        "format",
        '{"narrative_key":"已核验原文中真实出现的最短叙事实体",'
        '"one_line_meme":"普通人一句话就能复述的 meme",'
        '"event_role":"source","why_now":"此刻相对旧闻新增了什么",'
        '"unknowns":[]}',
    )
    result = search_narrative_brief(
        TwoStageGrok(_answer("search", "evidence"), echoed),
        "find it",
        instructions="search",
    )

    assert result.ok is False
    assert result.error == "grok_template_echo"
    assert result.repair_answer is echoed


def test_explicit_unknown_narrative_fails_closed() -> None:
    formatted = _answer(
        "format-unknown",
        '{"narrative_key":"unknown","one_line_meme":"unknown",'
        '"event_role":"unknown","why_now":"","unknowns":[]}',
    )

    result = search_narrative_brief(
        TwoStageGrok(_answer("search", "no public narrative"), formatted),
        "find it",
        instructions="search",
    )

    assert result.ok is False
    assert result.error == "grok_narrative_unknown"


def test_unsupported_formatter_enums_degrade_to_unknown() -> None:
    formatted = _answer(
        "format-enums",
        '{"narrative_key":"BTC bottom","one_line_meme":"Bottom is in",'
        '"event_role":"iambroots","phase":"narrative_source",'
        '"catalyst_type":"public_market_observation",'
        '"ca_carrier_status":null,"unknowns":[]}',
    )

    result = search_narrative_brief(
        TwoStageGrok(_answer("search", "verified public post"), formatted),
        "find it",
        instructions="search",
    )

    assert result.ok is True
    assert result.brief is not None
    assert result.brief.event_role.value == "unknown"
    assert result.brief.phase.value == "unknown"
    assert result.brief.catalyst_type.value == "unknown"
    assert result.brief.ca_carrier_status.value == "unknown"
