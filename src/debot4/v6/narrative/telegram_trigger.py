"""Investigate a newly monitored, exact public Telegram message."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from ..grok.briefs import GrokNarrativeBrief
from ..grok.leads import extract_x_status_leads
from ..grok.models import GrokSearchAnswer
from ..grok.prompts import SYSTEM, proactive_investigation_prompt
from ..grok.structured import GrokSearcher, search_narrative_brief
from ..telegram.models import TelegramPost
from .active_trigger import ActiveTriggerStatus
from .investigation_inputs import NarrativeEvent
from .trusted_ingest import TrustedIngestError, XStatusVerifier, events_from_verified_status
from .trusted_telegram import TelegramPostVerifier, events_from_verified_telegram


@dataclass(frozen=True, slots=True)
class TelegramNarrativeTrigger:
    channel: str
    message_id: int
    text: str
    event_at: datetime
    message_url: str

    @classmethod
    def from_post(cls, post: TelegramPost) -> "TelegramNarrativeTrigger":
        return cls(
            post.channel,
            post.message_id,
            post.text,
            post.created_at,
            post.canonical_url,
        )


@dataclass(frozen=True, slots=True)
class TelegramNarrativeResult:
    status: ActiveTriggerStatus
    reason: str
    trigger: TelegramNarrativeTrigger
    answer: GrokSearchAnswer | None = None
    brief: GrokNarrativeBrief | None = None
    events: tuple[NarrativeEvent, ...] = ()
    verified_urls: tuple[str, ...] = ()
    failed_urls: tuple[str, ...] = ()
    authorizes_trade: bool = False
    repair_answer: GrokSearchAnswer | None = None

    def __post_init__(self) -> None:
        if self.authorizes_trade:
            raise ValueError("Telegram narrative research cannot authorize a trade")


def investigate_telegram_trigger(
    trigger: TelegramNarrativeTrigger,
    *,
    grok: GrokSearcher,
    telegram_verifier: TelegramPostVerifier,
    x_verifier: XStatusVerifier,
    max_candidate_statuses: int = 12,
) -> TelegramNarrativeResult:
    """Verify the exact message, search context, then verify X evidence leads."""

    try:
        source = telegram_verifier.verify(trigger.channel, trigger.message_id)
    except (TrustedIngestError, ValueError) as exc:
        return _wait(trigger, f"trigger_unverified:{type(exc).__name__}")
    if _digest(source.text) != _digest(trigger.text):
        return _wait(trigger, "trigger_content_mismatch")
    searched = search_narrative_brief(
        grok,
        proactive_investigation_prompt(
            actor=source.actor.handle,
            event_text=trigger.text,
            event_at=trigger.event_at,
            event_url=trigger.message_url,
            actor_context=source.actor.to_payload(),
            post_type="telegram_channel_post",
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
    events = list(events_from_verified_telegram(source, brief.narrative_key))
    if not events:
        return _wait(
            trigger, "trigger_does_not_support_narrative_key", answer, brief
        )
    verified = [source.receipt.canonical_url]
    failed: list[str] = []
    for lead in extract_x_status_leads(answer)[:max_candidate_statuses]:
        try:
            status = x_verifier.verify(lead.canonical_url)
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
    return TelegramNarrativeResult(
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
    trigger: TelegramNarrativeTrigger,
    reason: str,
    answer: GrokSearchAnswer | None = None,
    brief: GrokNarrativeBrief | None = None,
    *,
    repair_answer: GrokSearchAnswer | None = None,
) -> TelegramNarrativeResult:
    return TelegramNarrativeResult(
        ActiveTriggerStatus.WAIT, reason, trigger, answer, brief,
        repair_answer=repair_answer,
    )


def _digest(text: str) -> str:
    return sha256(text.strip().encode()).hexdigest()
