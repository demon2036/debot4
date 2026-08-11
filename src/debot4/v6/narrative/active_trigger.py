"""Turn a newly monitored key-person post into a verified narrative package."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from hashlib import sha256
from debot4.v6.grok.briefs import GrokNarrativeBrief
from debot4.v6.grok.leads import extract_x_status_leads
from debot4.v6.grok.models import GrokSearchAnswer
from debot4.v6.grok.prompts import SYSTEM, proactive_investigation_prompt
from debot4.v6.grok.structured import GrokSearcher, search_narrative_brief
from debot4.v6.x.models import XPost

from .investigation_inputs import NarrativeEvent
from .trusted_ingest import (
    TrustedIngestError,
    XStatusVerifier,
    events_from_verified_status,
)


class ActiveTriggerStatus(str, Enum):
    READY = "READY"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class ActiveNarrativeTrigger:
    tweet_id: str
    actor_handle: str
    text: str
    event_at: datetime
    status_url: str
    post_type: str
    target_author: str = ""
    target_text: str = ""

    @classmethod
    def from_post(cls, post: XPost) -> "ActiveNarrativeTrigger":
        return cls(
            post.tweet_id,
            post.author,
            post.text,
            post.created_at,
            post.canonical_url,
            post.post_type,
            post.target_author,
            post.target_text,
        )


@dataclass(frozen=True, slots=True)
class ActiveNarrativeResult:
    status: ActiveTriggerStatus
    reason: str
    trigger: ActiveNarrativeTrigger
    answer: GrokSearchAnswer | None = None
    brief: GrokNarrativeBrief | None = None
    events: tuple[NarrativeEvent, ...] = ()
    verified_urls: tuple[str, ...] = ()
    failed_urls: tuple[str, ...] = ()
    authorizes_trade: bool = False
    repair_answer: GrokSearchAnswer | None = None

    def __post_init__(self) -> None:
        if self.authorizes_trade:
            raise ValueError("active narrative research cannot authorize a trade")


def investigate_active_trigger(
    trigger: ActiveNarrativeTrigger,
    *,
    grok: GrokSearcher,
    verifier: XStatusVerifier,
    max_candidate_statuses: int = 12,
) -> ActiveNarrativeResult:
    """Verify trigger, force Grok search, then independently verify every X lead."""

    try:
        source = verifier.verify(trigger.status_url)
    except (TrustedIngestError, ValueError) as exc:
        return _wait(trigger, f"trigger_unverified:{type(exc).__name__}")
    if _digest(source.text) != _digest(trigger.text):
        return _wait(trigger, "trigger_content_mismatch")
    searched = search_narrative_brief(
        grok,
        proactive_investigation_prompt(
            actor=trigger.actor_handle,
            event_text=trigger.text,
            event_at=trigger.event_at,
            event_url=trigger.status_url,
            actor_context=source.actor.to_payload(),
            post_type=trigger.post_type,
            target_author=trigger.target_author,
            target_text=trigger.target_text,
        ),
        instructions=SYSTEM,
    )
    if not searched.ok:
        return _wait(
            trigger, searched.error, searched.answer,
            repair_answer=searched.repair_answer,
        )
    answer = searched.answer
    brief = searched.brief
    assert answer is not None and brief is not None
    leads = extract_x_status_leads(answer)
    if not leads:
        return _wait(trigger, "grok_returned_no_verifiable_x_status", answer, brief)
    events = list(events_from_verified_status(source, brief.narrative_key))
    if not events:
        return _wait(trigger, "trigger_does_not_support_narrative_key", answer, brief)
    verified = [source.receipt.canonical_url]
    failed: list[str] = []
    for lead in leads[:max_candidate_statuses]:
        if lead.status_id == source.receipt.source_id:
            continue
        try:
            status = verifier.verify(lead.canonical_url)
            derived = events_from_verified_status(status, brief.narrative_key)
        except (TrustedIngestError, ValueError):
            failed.append(lead.canonical_url)
            continue
        if derived:
            events.extend(derived)
            verified.append(status.receipt.canonical_url)
        else:
            failed.append(lead.canonical_url)
    unique = {item.event_id: item for item in events}
    return ActiveNarrativeResult(
        ActiveTriggerStatus.READY,
        "verified_narrative_package",
        trigger,
        answer,
        brief,
        tuple(unique.values()),
        tuple(dict.fromkeys(verified)),
        tuple(dict.fromkeys(failed)),
        repair_answer=searched.repair_answer,
    )


def _wait(
    trigger: ActiveNarrativeTrigger,
    reason: str,
    answer: GrokSearchAnswer | None = None,
    brief: GrokNarrativeBrief | None = None,
    *,
    repair_answer: GrokSearchAnswer | None = None,
) -> ActiveNarrativeResult:
    return ActiveNarrativeResult(
        ActiveTriggerStatus.WAIT, reason, trigger, answer, brief,
        repair_answer=repair_answer,
    )


def _digest(text: str) -> str:
    return sha256(text.strip().encode()).hexdigest()
