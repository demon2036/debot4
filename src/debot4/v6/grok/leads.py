"""Convert Grok search output into untrusted, deduplicated X status leads."""

from __future__ import annotations

from dataclasses import dataclass

from debot4.v6.narrative.fxtwitter import FxTwitterError, parse_x_status_url

from .models import GrokSearchAnswer


@dataclass(frozen=True, slots=True)
class GrokXLead:
    """A discovery hint. It is deliberately not narrative evidence."""

    response_id: str
    handle: str
    status_id: str
    candidate_url: str

    @property
    def canonical_url(self) -> str:
        return f"https://x.com/{self.handle}/status/{self.status_id}"


def extract_x_status_leads(answer: GrokSearchAnswer) -> tuple[GrokXLead, ...]:
    """Keep only exact, numeric X status URLs and remove duplicate tweet IDs."""

    leads: list[GrokXLead] = []
    seen: set[str] = set()
    for candidate in answer.candidate_urls:
        try:
            handle, status_id = parse_x_status_url(candidate)
        except FxTwitterError:
            continue
        if status_id in seen:
            continue
        leads.append(GrokXLead(answer.response_id, handle, status_id, candidate))
        seen.add(status_id)
    return tuple(leads)
