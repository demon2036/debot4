"""Separate evidence search from bounded, evidence-neutral JSON formatting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .briefs import GrokBriefError, GrokNarrativeBrief, parse_narrative_brief
from .formatter_normalize import normalize_formatter_enums
from .models import GrokSearchAnswer
from .prompts import (
    FORMAT_REPAIR_SYSTEM,
    contains_template_echo,
    format_repair_prompt,
)


class GrokSearcher(Protocol):
    def search(self, prompt: str, *, instructions: str) -> GrokSearchAnswer: ...

    def format_json(
        self, prompt: str, *, instructions: str
    ) -> GrokSearchAnswer: ...


@dataclass(frozen=True, slots=True)
class StructuredNarrativeSearch:
    """Search answer is authoritative; format output can only shape the brief."""

    answer: GrokSearchAnswer | None
    brief: GrokNarrativeBrief | None
    repair_answer: GrokSearchAnswer | None = None
    error: str = ""

    def __post_init__(self) -> None:
        if bool(self.brief) == bool(self.error):
            raise ValueError("structured Grok result needs either a brief or an error")
        if self.answer is None and self.repair_answer is not None:
            raise ValueError("format answer cannot exist without the search answer")

    @property
    def ok(self) -> bool:
        return self.brief is not None


def search_narrative_brief(
    searcher: GrokSearcher,
    prompt: str,
    *,
    instructions: str,
) -> StructuredNarrativeSearch:
    """Fail closed while retaining every model response for later audit."""

    try:
        search_x = getattr(searcher, "search_x", None)
        answer = (
            search_x(prompt, instructions=instructions)
            if callable(search_x)
            else searcher.search(prompt, instructions=instructions)
        )
    except Exception:
        return StructuredNarrativeSearch(None, None, error="grok_search_failed")
    formatter = getattr(searcher, "format_json", None)
    if not callable(formatter):
        return StructuredNarrativeSearch(
            answer, None, error="grok_format_unavailable"
        )
    try:
        repaired = formatter(
            format_repair_prompt(answer.text),
            instructions=FORMAT_REPAIR_SYSTEM,
        )
    except Exception:
        return StructuredNarrativeSearch(answer, None, error="grok_format_failed")
    if contains_template_echo(repaired.text):
        return StructuredNarrativeSearch(
            answer, None, repaired, "grok_template_echo"
        )
    try:
        brief = parse_narrative_brief(repaired.text)
    except (GrokBriefError, ValueError):
        try:
            normalized = normalize_formatter_enums(repaired.text)
            brief = parse_narrative_brief(normalized)
        except (GrokBriefError, ValueError):
            return StructuredNarrativeSearch(
                answer, None, repaired, "grok_brief_invalid",
            )
    if (
        brief.narrative_key.casefold() == "unknown"
        or brief.one_line_meme.casefold() == "unknown"
    ):
        return StructuredNarrativeSearch(
            answer, None, repaired, "grok_narrative_unknown"
        )
    return StructuredNarrativeSearch(answer, brief, repaired)
