"""Bounded Grok request policies and retry execution."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import math
import time
from typing import Mapping

from .transport import GrokApiError, JsonTransport


@dataclass(frozen=True, slots=True)
class GrokRequestPolicy:
    """One explicit latency budget for one kind of model work."""

    timeout_seconds: float
    attempts: int = 1
    web_search: bool = True

    def __post_init__(self) -> None:
        if not math.isfinite(self.timeout_seconds) or self.timeout_seconds <= 0:
            raise ValueError("Grok request timeout must be positive and finite")
        if isinstance(self.attempts, bool) or not 1 <= self.attempts <= 5:
            raise ValueError("Grok request attempts must be between 1 and 5")


REALTIME_SEARCH = GrokRequestPolicy(90.0)
DISCOVERY_SEARCH = GrokRequestPolicy(170.0)
FORMAT_ONLY = GrokRequestPolicy(30.0, web_search=False)


def execute_chat(
    transport: JsonTransport,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    instructions: str,
    policy: GrokRequestPolicy,
) -> Mapping[str, object]:
    """Execute one policy-bounded request without leaking credentials."""

    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": instructions},
            {"role": "user", "content": prompt},
        ],
    }
    if policy.web_search:
        payload["tools"] = [{"type": "web_search"}]
        payload["tool_choice"] = "required"
    return _execute(
        transport,
        url=f"{base_url}/v1/chat/completions",
        api_key=api_key,
        payload=payload,
        policy=policy,
    )


def execute_x_search(
    transport: JsonTransport,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    instructions: str,
    policy: GrokRequestPolicy,
) -> Mapping[str, object]:
    """Execute Grok's native X search through the Responses endpoint."""

    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "store": False,
        "instructions": instructions,
        "input": prompt,
        "tools": [{"type": "x_search"}],
        "tool_choice": "required",
    }
    return _execute(
        transport,
        url=f"{base_url}/v1/responses",
        api_key=api_key,
        payload=payload,
        policy=policy,
    )


def execute_response(
    transport: JsonTransport,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    instructions: str,
    policy: GrokRequestPolicy,
    max_output_tokens: int = 32,
) -> Mapping[str, object]:
    """Execute a compact, tool-free Responses API classification."""

    if isinstance(max_output_tokens, bool) or not 1 <= max_output_tokens <= 512:
        raise ValueError("response token limit must be between 1 and 512")
    return _execute(
        transport,
        url=f"{base_url}/v1/responses",
        api_key=api_key,
        payload={
            "model": model,
            "stream": False,
            "store": False,
            "instructions": instructions,
            "input": prompt,
            "reasoning": {"effort": "low"},
            "max_output_tokens": max_output_tokens,
        },
        policy=policy,
    )


def execute_image_chat(
    transport: JsonTransport,
    *,
    base_url: str,
    api_key: str,
    model: str,
    prompt: str,
    instructions: str,
    image: bytes,
    media_type: str,
    policy: GrokRequestPolicy,
) -> Mapping[str, object]:
    """Analyze exact caller-supplied image bytes without granting web search."""

    encoded = base64.b64encode(image).decode("ascii")
    payload: dict[str, object] = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": instructions},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{media_type};base64,{encoded}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
    }
    return _execute(
        transport,
        url=f"{base_url}/v1/chat/completions",
        api_key=api_key,
        payload=payload,
        policy=policy,
    )


def _execute(
    transport: JsonTransport,
    *,
    url: str,
    api_key: str,
    payload: Mapping[str, object],
    policy: GrokRequestPolicy,
) -> Mapping[str, object]:
    last_error: GrokApiError | None = None
    for attempt in range(policy.attempts):
        try:
            return transport.post_json(
                url,
                {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                payload,
                policy.timeout_seconds,
            )
        except GrokApiError as exc:
            last_error = exc
            if not exc.retryable or attempt + 1 >= policy.attempts:
                break
            time.sleep(min(0.25 * (2**attempt), 1.0))
    raise last_error or GrokApiError("Grok2API request failed")
