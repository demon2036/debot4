from __future__ import annotations

from datetime import timedelta
import json

import pytest

from debot4.v6.narrative.mint_qualification import (
    MINT_QUALIFIER_MODEL,
    MintQualificationAction,
)
from debot4.v6.narrative.spark_mint_qualifier import SparkMintQualifier
from tests.v6_catalyst_mint_samples import BUDUJIN_OBSERVED_AT, budujin_match


class _Transport:
    def __init__(self, *answers: str) -> None:
        self.answers = list(answers)
        self.calls: list[tuple[str, dict, dict, float]] = []

    def post_json(self, url, headers, payload, timeout_seconds):
        self.calls.append((url, dict(headers), dict(payload), timeout_seconds))
        answer = self.answers.pop(0)
        return {
            "id": "response-1",
            "model": MINT_QUALIFIER_MODEL,
            "output": [{
                "type": "message",
                "content": [{
                    "type": "output_text", "text": answer, "annotations": [],
                }],
            }],
            "usage": {"input_tokens": 10, "output_tokens": 1},
        }


def test_qualifier_sends_exact_post_and_debot_mint_without_search() -> None:
    transport = _Transport("A")
    times = iter((
        BUDUJIN_OBSERVED_AT,
        BUDUJIN_OBSERVED_AT + timedelta(milliseconds=900),
    ))
    qualifier = SparkMintQualifier(
        "secret", transport=transport, clock=lambda: next(times)
    )

    result = qualifier.qualify(budujin_match())

    assert result.action is MintQualificationAction.ALERT
    assert result.model == MINT_QUALIFIER_MODEL
    assert result.latency_seconds == 0.9
    url, headers, payload, timeout = transport.calls[0]
    assert url == "http://127.0.0.1:8339/v1/responses"
    assert headers["Authorization"] == "Bearer secret"
    assert payload["model"] == MINT_QUALIFIER_MODEL
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["max_output_tokens"] == 32
    assert "tools" not in payload
    assert timeout == 7.0
    evidence = json.loads(payload["input"])
    assert evidence["x_post"]["text"] == budujin_match().catalyst_text
    assert evidence["debot_mint"]["exact_ca"] == budujin_match().exact_ca
    assert evidence["debot_mint"]["stage"] == "completing"
    assert evidence["debot_mint"]["provider_fdv_usd"] == "5000"


def test_qualifier_rejects_and_fails_closed_on_invalid_output() -> None:
    rejected = SparkMintQualifier(
        "secret", transport=_Transport("R"), clock=lambda: BUDUJIN_OBSERVED_AT
    ).qualify(budujin_match())
    assert rejected.action is MintQualificationAction.REJECT

    qualifier = SparkMintQualifier(
        "secret", transport=_Transport("maybe"),
        clock=lambda: BUDUJIN_OBSERVED_AT,
    )
    with pytest.raises(RuntimeError, match="invalid verdict"):
        qualifier.qualify(budujin_match())


def test_optional_configuration_requires_a_credential() -> None:
    assert SparkMintQualifier.from_env_optional(environ={}) is None

    qualifier = SparkMintQualifier.from_env_optional(
        environ={"DEBOT4_MINT_QUALIFIER_KEY": " secret "},
        transport=_Transport("R"),
    )
    assert qualifier is not None
    assert qualifier.api_key == "secret"
    assert "secret" not in repr(qualifier)
