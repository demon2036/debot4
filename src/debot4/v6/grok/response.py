"""Parse Grok2API responses while retaining auditable source URLs."""

from __future__ import annotations

import re
from typing import Mapping

from .models import GrokCitation, GrokSearchAnswer, GrokSearchSource
from .transport import GrokApiError


_ABSOLUTE_URL = re.compile(r"https?://[^\s<>\]\[(){}\"']+")


def parse_answer(
    payload: Mapping[str, object], requested_model: str
) -> GrokSearchAnswer:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise GrokApiError("Grok2API response has no choices")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise GrokApiError("Grok2API response has no answer text")
    citations = _parse_citations(message.get("annotations"))
    sources = _parse_sources(payload.get("search_sources"), citations)
    return GrokSearchAnswer(
        str(payload.get("id") or "unknown"),
        str(payload.get("model") or requested_model),
        message["content"],
        sources,
        citations,
        _extract_candidate_urls(message["content"], sources, citations),
        _clean_usage(payload.get("usage")),
    )


def parse_responses_answer(
    payload: Mapping[str, object], requested_model: str
) -> GrokSearchAnswer:
    """Parse the Responses API while retaining native X search evidence."""

    output = payload.get("output")
    if not isinstance(output, list):
        raise GrokApiError("Grok2API response has no output")
    texts: list[str] = []
    raw_sources: list[object] = []
    raw_citations: list[object] = []
    for item in output:
        if not isinstance(item, dict):
            continue
        if item.get("type") in {"x_search_call", "web_search_call"}:
            action = item.get("action")
            if isinstance(action, dict) and isinstance(action.get("sources"), list):
                raw_sources.extend(_tag_sources(action["sources"], str(item["type"])))
        if item.get("type") != "message" or not isinstance(item.get("content"), list):
            continue
        for content in item["content"]:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text)
            annotations = content.get("annotations")
            if isinstance(annotations, list):
                raw_citations.extend(annotations)
    top_citations = payload.get("citations")
    if isinstance(top_citations, list):
        raw_citations.extend(top_citations)
    answer_text = "\n".join(texts).strip()
    if not answer_text:
        raise GrokApiError("Grok2API response has no answer text")
    citations = _parse_citations(raw_citations)
    sources = _parse_sources(raw_sources, citations)
    return GrokSearchAnswer(
        str(payload.get("id") or "unknown"),
        str(payload.get("model") or requested_model),
        answer_text,
        sources,
        citations,
        _extract_candidate_urls(answer_text, sources, citations),
        _clean_usage(payload.get("usage")),
    )


def _tag_sources(raw: list[object], source_type: str) -> list[object]:
    tagged: list[object] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        value = dict(item)
        value.setdefault("source_type", source_type)
        tagged.append(value)
    return tagged


def _parse_sources(
    raw: object,
    citations: tuple[GrokCitation, ...],
) -> tuple[GrokSearchSource, ...]:
    sources: list[GrokSearchSource] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            url = item["url"].strip()
            if not url or url in seen:
                continue
            try:
                source = GrokSearchSource(
                    url,
                    str(item.get("title") or ""),
                    str(item.get("source_type") or item.get("type") or "web"),
                )
            except ValueError:
                continue
            sources.append(source)
            seen.add(url)
    for citation in citations:
        if citation.url not in seen:
            sources.append(GrokSearchSource(citation.url, citation.title, "citation"))
            seen.add(citation.url)
    return tuple(sources)


def _parse_citations(raw: object) -> tuple[GrokCitation, ...]:
    citations: list[GrokCitation] = []
    seen: set[tuple[str, int | None, int | None]] = set()
    if not isinstance(raw, list):
        return ()
    for item in raw:
        if isinstance(item, str):
            item = {"url": item}
        if not isinstance(item, dict):
            continue
        value = item.get("url_citation", item)
        if not isinstance(value, dict) or not isinstance(value.get("url"), str):
            continue
        start = value.get("start_index")
        end = value.get("end_index")
        start = start if isinstance(start, int) and not isinstance(start, bool) else None
        end = end if isinstance(end, int) and not isinstance(end, bool) else None
        key = (value["url"].strip(), start, end)
        if not key[0] or key in seen:
            continue
        try:
            citations.append(GrokCitation(
                key[0], str(value.get("title") or ""), start, end
            ))
        except ValueError:
            continue
        seen.add(key)
    return tuple(citations)


def _clean_usage(raw: object) -> dict[str, int]:
    return {
        key: int(value)
        for key, value in (raw.items() if isinstance(raw, dict) else ())
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
    }


def _extract_candidate_urls(
    text: str,
    sources: tuple[GrokSearchSource, ...],
    citations: tuple[GrokCitation, ...],
) -> tuple[str, ...]:
    urls = [item.url for item in sources]
    urls.extend(item.url for item in citations)
    urls.extend(match.rstrip(".,;:!?*_~`") for match in _ABSOLUTE_URL.findall(text))
    valid: list[str] = []
    for url in dict.fromkeys(urls):
        try:
            GrokSearchSource(url, "candidate", "candidate")
        except ValueError:
            continue
        valid.append(url)
    return tuple(valid)
