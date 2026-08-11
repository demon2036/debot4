from __future__ import annotations

from typing import Mapping

from debot4.v6.grok import Grok2ApiClient


class FakeTransport:
    def __init__(self, response: Mapping[str, object]) -> None:
        self.response = response
        self.calls: list[
            tuple[str, Mapping[str, str], Mapping[str, object], float]
        ] = []

    def post_json(self, url, headers, payload, timeout_seconds):
        self.calls.append((url, headers, payload, timeout_seconds))
        return self.response


def test_native_x_search_uses_responses_endpoint_and_keeps_sources() -> None:
    transport = FakeTransport(
        {
            "id": "resp-1",
            "model": "grok-chat-fast",
            "output": [
                {
                    "type": "x_search_call",
                    "action": {
                        "query": "from:yeonwoo1102 meme",
                        "sources": [
                            {
                                "url": "https://x.com/yeonwoo1102/status/1",
                                "title": "Yeon",
                            }
                        ],
                    },
                },
                {
                    "type": "message",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Yeon discussed this meme.",
                            "annotations": [
                                {
                                    "type": "url_citation",
                                    "url": "https://x.com/yeonwoo1102/status/1",
                                    "title": "Yeon post",
                                    "start_index": 0,
                                    "end_index": 4,
                                }
                            ],
                        }
                    ],
                },
            ],
            "citations": ["https://x.com/yeonwoo1102/status/2"],
            "usage": {"input_tokens": 10, "output_tokens": 5, "bad": True},
        }
    )
    client = Grok2ApiClient("secret", transport=transport)

    answer = client.search_x("find posts", instructions="use native X search")

    assert answer.response_id == "resp-1"
    assert answer.text == "Yeon discussed this meme."
    assert [source.url for source in answer.sources] == [
        "https://x.com/yeonwoo1102/status/1",
        "https://x.com/yeonwoo1102/status/2",
    ]
    assert answer.sources[0].source_type == "x_search_call"
    assert answer.usage == {"input_tokens": 10, "output_tokens": 5}
    url, headers, payload, timeout = transport.calls[0]
    assert url == "http://127.0.0.1:8000/v1/responses"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["stream"] is False
    assert payload["store"] is False
    assert payload["tools"] == [{"type": "x_search"}]
    assert payload["tool_choice"] == "required"
    assert timeout == 90.0
