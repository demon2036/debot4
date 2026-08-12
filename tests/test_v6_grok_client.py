from __future__ import annotations

from datetime import datetime, timezone
from typing import Mapping

import pytest

from debot4.v6.grok import (
    Grok2ApiClient,
    GrokApiError,
    passive_investigation_prompt,
    proactive_investigation_prompt,
)


class FakeTransport:
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, Mapping[str, str], Mapping[str, object], float]] = []

    def post_json(self, url, headers, payload, timeout_seconds):
        self.calls.append((url, headers, payload, timeout_seconds))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def _response() -> dict[str, object]:
    return {
        "id": "chatcmpl-1",
        "model": "grok-chat-fast",
        "choices": [
            {
                "message": {
                    "content": (
                        "事实: 原帖没有 CA; candidate "
                        "https://x.com/cz_binance/status/3."
                    ),
                    "annotations": [
                        {
                            "type": "url_citation",
                            "url_citation": {
                                "url": "https://x.com/BNBCHAIN/status/2",
                                "title": "BNB Chain",
                                "start_index": 4,
                                "end_index": 10,
                            },
                        }
                    ],
                }
            }
        ],
        "search_sources": [
            {"url": "https://x.com/cz_binance/status/1", "title": "CZ", "source_type": "x"},
            {"url": "https://x.com/cz_binance/status/1", "title": "duplicate"},
            {"url": "javascript:alert(1)", "title": "bad"},
        ],
        "usage": {"prompt_tokens": 12, "completion_tokens": 8, "bad": True},
    }


def test_direct_client_uses_non_streaming_hosted_search_and_keeps_sources() -> None:
    transport = FakeTransport([_response()])
    client = Grok2ApiClient("secret", transport=transport)

    answer = client.search("find source", instructions="verify URLs")

    assert answer.text.startswith("事实: 原帖没有 CA")
    assert [item.url for item in answer.sources] == [
        "https://x.com/cz_binance/status/1",
        "https://x.com/BNBCHAIN/status/2",
    ]
    assert answer.citations[0].start_index == 4
    assert answer.candidate_urls == (
        "https://x.com/cz_binance/status/1",
        "https://x.com/BNBCHAIN/status/2",
        "https://x.com/cz_binance/status/3",
    )
    assert answer.usage == {"prompt_tokens": 12, "completion_tokens": 8}
    url, headers, payload, _ = transport.calls[0]
    assert url == "http://127.0.0.1:8000/v1/chat/completions"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["stream"] is False
    assert payload["tools"] == [{"type": "web_search"}]
    assert payload["tool_choice"] == "required"


def test_candidate_url_strips_markdown_emphasis() -> None:
    response = _response()
    response["choices"][0]["message"]["content"] = (
        "**https://x.com/cz_binance/status/1890071433214038103**"
    )
    client = Grok2ApiClient("secret", transport=FakeTransport([response]))

    answer = client.search("find", instructions="verify")

    assert "https://x.com/cz_binance/status/1890071433214038103" in (
        answer.candidate_urls
    )


def test_client_retries_sanitized_transport_failure() -> None:
    transport = FakeTransport([
        GrokApiError("temporary", retryable=True),
        _response(),
    ])
    client = Grok2ApiClient("secret", attempts=2, transport=transport)

    assert client.search("find", instructions="verify").response_id == "chatcmpl-1"
    assert len(transport.calls) == 2


def test_client_does_not_replay_non_retryable_failure() -> None:
    transport = FakeTransport([GrokApiError("unauthorized"), _response()])
    client = Grok2ApiClient("secret", attempts=2, transport=transport)

    with pytest.raises(GrokApiError, match="unauthorized"):
        client.search("find", instructions="verify")

    assert len(transport.calls) == 1


def test_client_defaults_to_single_fast_realtime_attempt() -> None:
    client = Grok2ApiClient("secret", transport=FakeTransport([_response()]))

    client.search("find", instructions="verify")

    assert client.timeout_seconds == 90.0
    assert client.attempts == 1
    assert client.transport.calls[0][3] == 90.0


def test_discovery_lane_is_single_bounded_web_search() -> None:
    transport = FakeTransport([_response()])
    client = Grok2ApiClient("secret", transport=transport)

    client.search_discovery("find history", instructions="verify")

    payload = transport.calls[0][2]
    assert transport.calls[0][3] == 170.0
    assert payload["tool_choice"] == "required"


def test_format_lane_never_uses_web_search() -> None:
    transport = FakeTransport([_response()])
    client = Grok2ApiClient("secret", transport=transport)

    client.format_json("repair", instructions="only format")

    payload = transport.calls[0][2]
    assert transport.calls[0][3] == 30.0
    assert "tools" not in payload
    assert "tool_choice" not in payload


def test_image_lane_sends_exact_bytes_without_search() -> None:
    transport = FakeTransport([_response()])
    client = Grok2ApiClient("secret", transport=transport)

    client.analyze_image(
        "read rows", image=b"jpeg", media_type="image/jpeg", instructions="literal",
    )

    payload = transport.calls[0][2]
    content = payload["messages"][1]["content"]
    assert content[1]["image_url"]["url"] == "data:image/jpeg;base64,anBlZw=="
    assert "tools" not in payload


def test_client_rejects_missing_answer() -> None:
    client = Grok2ApiClient("secret", transport=FakeTransport([{"choices": []}]))

    with pytest.raises(GrokApiError, match="no choices"):
        client.search("find", instructions="verify")


def test_client_repr_never_exposes_api_key() -> None:
    client = Grok2ApiClient("super-secret", transport=FakeTransport([_response()]))

    assert "super-secret" not in repr(client)


def test_client_from_env_reads_bounded_key_file(monkeypatch, tmp_path) -> None:
    key_file = tmp_path / "grok.key"
    key_file.write_text("  file-secret\n", encoding="utf-8")
    monkeypatch.delenv("DEBOT4_GROK2API_KEY", raising=False)
    monkeypatch.setenv("DEBOT4_GROK2API_KEY_FILE", str(key_file))
    monkeypatch.setenv("DEBOT4_GROK2API_BASE_URL", "https://grok.internal/")
    monkeypatch.setenv("DEBOT4_GROK2API_MODEL", "grok-search")
    monkeypatch.setenv("DEBOT4_GROK2API_TIMEOUT_SECONDS", "175")

    client = Grok2ApiClient.from_env(transport=FakeTransport([_response()]))

    assert client.api_key == "file-secret"
    assert client.base_url == "https://grok.internal"
    assert client.model == "grok-search"
    assert client.timeout_seconds == 175.0
    assert "file-secret" not in repr(client)


def test_client_rejects_non_numeric_timeout_from_env(monkeypatch) -> None:
    monkeypatch.setenv("DEBOT4_GROK2API_KEY", "secret")
    monkeypatch.setenv("DEBOT4_GROK2API_TIMEOUT_SECONDS", "later")

    with pytest.raises(ValueError, match="must be numeric"):
        Grok2ApiClient.from_env()


def test_direct_env_key_wins_without_reading_key_file(monkeypatch, tmp_path) -> None:
    missing_file = tmp_path / "must-not-be-read"
    monkeypatch.setenv("DEBOT4_GROK2API_KEY", " direct-secret ")
    monkeypatch.setenv("DEBOT4_GROK2API_KEY_FILE", str(missing_file))

    client = Grok2ApiClient.from_env(transport=FakeTransport([_response()]))

    assert client.api_key == "direct-secret"


@pytest.mark.parametrize(
    ("contents", "message"),
    [
        (b" \n\t", "is empty"),
        (b"x" * 4097, "exceeds 4096 bytes"),
        (b"\xff", "must contain UTF-8 text"),
    ],
)
def test_key_file_rejects_invalid_content_without_echoing_it(
    monkeypatch, tmp_path, contents, message
) -> None:
    key_file = tmp_path / "private-api-key"
    key_file.write_bytes(contents)
    monkeypatch.delenv("DEBOT4_GROK2API_KEY", raising=False)
    monkeypatch.setenv("DEBOT4_GROK2API_KEY_FILE", str(key_file))

    with pytest.raises(ValueError, match=message) as error:
        Grok2ApiClient.from_env()

    assert str(key_file) not in str(error.value)


def test_explicit_from_env_overrides_take_priority(monkeypatch) -> None:
    monkeypatch.setenv("DEBOT4_GROK2API_KEY", "env-secret")
    monkeypatch.setenv("DEBOT4_GROK2API_BASE_URL", "https://env.invalid")
    monkeypatch.setenv("DEBOT4_GROK2API_MODEL", "env-model")

    client = Grok2ApiClient.from_env(
        api_key="explicit-secret",
        base_url="https://explicit.invalid",
        model="explicit-model",
        transport=FakeTransport([_response()]),
    )

    assert client.api_key == "explicit-secret"
    assert client.base_url == "https://explicit.invalid"
    assert client.model == "explicit-model"


def test_two_prompts_preserve_causal_direction_and_endorsement_boundary() -> None:
    now = datetime(2026, 8, 9, tzinfo=timezone.utc)
    proactive = proactive_investigation_prompt(
        actor="@cz_binance",
        event_text="test",
        event_at=now,
        actor_context={"tier": "ecosystem_authority", "capabilities": []},
        post_type="reply",
        target_author="elonmusk",
    )
    passive = passive_investigation_prompt(
        token_address="0x" + "1" * 40, anomaly="volume spike", observed_at=now
    )

    assert "原帖没有 CA" in proactive
    assert "最多列 3 个已有直接证据的竞争 CA" in proactive
    assert "propagation_kol 只能提供传播线索" in proactive
    assert "事件类型: reply" in proactive
    assert "从异动时间向前搜索" in passive
    assert "禁止把后发帖倒灌成原因" in passive
