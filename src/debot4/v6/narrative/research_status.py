"""Small safe summaries extracted from private research documents."""

from __future__ import annotations

import json
from typing import Any, Mapping
from urllib.parse import urlsplit

from ..grok.prompts import contains_template_echo


def summarize_research_document(raw: str) -> dict[str, object]:
    """Expose only reviewed display fields; never return model answer bodies."""

    try:
        document = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return _empty()
    root = _mapping(document)
    research = _mapping(root.get("research"))
    trigger = _mapping(research.get("trigger"))
    result = _mapping(research.get("result"))
    brief = _mapping(result.get("brief"))
    summary = {
        "subject": _subject(trigger),
        "source_url": _source_url(trigger),
        "exact_ca": _text(trigger.get("exact_ca"), 96),
        "narrative_key": _text(brief.get("narrative_key"), 160),
        "one_line_meme": _text(brief.get("one_line_meme"), 280),
        "why_now": _text(brief.get("why_now"), 400),
        "phase": _text(brief.get("phase"), 40),
        "verified_urls": _urls(result.get("verified_urls")),
        "quality": "reviewed",
    }
    if contains_template_echo(json.dumps(brief, ensure_ascii=False)):
        summary.update({
            "narrative_key": "",
            "one_line_meme": "",
            "why_now": "",
            "phase": "",
            "quality": "invalid_template_echo",
        })
    return summary


def _empty() -> dict[str, object]:
    return {
        "subject": "",
        "source_url": "",
        "exact_ca": "",
        "narrative_key": "",
        "one_line_meme": "",
        "why_now": "",
        "phase": "",
        "verified_urls": [],
        "quality": "unavailable",
    }


def _subject(trigger: Mapping[str, Any]) -> str:
    actor = _text(trigger.get("actor_handle"), 40)
    if actor:
        return f"@{actor}"
    channel = _text(trigger.get("channel"), 80)
    if channel:
        return f"TG @{channel}"
    symbol = _text(trigger.get("token_symbol"), 40)
    name = _text(trigger.get("token_name"), 120)
    return symbol or name or _text(trigger.get("signal_id"), 80)


def _source_url(trigger: Mapping[str, Any]) -> str:
    for key in ("status_url", "message_url"):
        value = _safe_url(trigger.get(key))
        if value:
            return value
    social = trigger.get("social_urls")
    if isinstance(social, list):
        for value in social:
            safe = _safe_url(value)
            if safe:
                return safe
    return ""


def _urls(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    output = []
    for item in value[:12]:
        safe = _safe_url(item)
        if safe and safe not in output:
            output.append(safe)
    return output


def _safe_url(value: object) -> str:
    text = _text(value, 500)
    try:
        parsed = urlsplit(text)
    except ValueError:
        return ""
    return text if parsed.scheme == "https" and bool(parsed.hostname) else ""


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _text(value: object, limit: int) -> str:
    return value.strip()[:limit] if isinstance(value, str) else ""
