"""Verify Grok-discovered X leads for one passive narrative hypothesis."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from ..grok.briefs import GrokNarrativeBrief
from ..grok.leads import GrokXLead, extract_x_status_leads
from ..grok.models import GrokSearchAnswer
from .investigation_inputs import NarrativeEvent
from .trusted_ingest import (
    VerifiedXStatus,
    XStatusVerifier,
    events_from_verified_status,
)


@dataclass(frozen=True, slots=True)
class PassiveEvidence:
    leads: tuple[GrokXLead, ...]
    events: tuple[NarrativeEvent, ...]
    verified_urls: tuple[str, ...]
    failed_urls: tuple[str, ...]


def passive_answer_audit(answer: GrokSearchAnswer | None) -> dict[str, object] | None:
    if answer is None:
        return None
    return {
        "response_id": answer.response_id,
        "model": answer.model,
        "text_sha256": sha256(answer.text.encode("utf-8")).hexdigest(),
        "source_urls": [item.url for item in answer.sources],
        "citation_urls": [item.url for item in answer.citations],
        "candidate_urls": list(answer.candidate_urls),
    }


def verify_passive_evidence(
    answer: GrokSearchAnswer,
    brief: GrokNarrativeBrief,
    verifier: XStatusVerifier,
    *,
    seed_statuses: tuple[VerifiedXStatus, ...] = (),
    max_candidate_statuses: int = 12,
) -> PassiveEvidence:
    """Treat Grok as a locator; only sealed FxTwitter observations become events."""

    supported = {item.url for item in answer.sources}
    supported.update(item.url for item in answer.citations)
    leads = tuple(
        item for item in extract_x_status_leads(answer)
        if item.candidate_url in supported or item.canonical_url in supported
    )[:max_candidate_statuses]
    events: dict[str, NarrativeEvent] = {}
    verified: list[str] = []
    failed: list[str] = []
    checked: set[str] = set()
    for status in seed_statuses:
        url = status.receipt.canonical_url
        checked.add(url.casefold())
        verified.append(url)
        derived = events_from_verified_status(status, brief.narrative_key)
        events.update((item.event_id, item) for item in derived)
    for lead in leads:
        if lead.canonical_url.casefold() in checked:
            continue
        checked.add(lead.canonical_url.casefold())
        try:
            status = verifier.verify(lead.canonical_url)
            derived = events_from_verified_status(status, brief.narrative_key)
        except Exception:
            failed.append(lead.canonical_url)
            continue
        if not derived:
            failed.append(lead.canonical_url)
            continue
        verified.append(status.receipt.canonical_url)
        events.update((item.event_id, item) for item in derived)
    ordered = tuple(sorted(
        events.values(),
        key=lambda item: (item.published_at, item.event_id),
    ))
    return PassiveEvidence(
        leads,
        ordered,
        tuple(dict.fromkeys(verified)),
        tuple(dict.fromkeys(failed)),
    )
