"""JSON-safe serializers for narrative research dependencies."""

from __future__ import annotations

from hashlib import sha256

from ..grok.briefs import CaReference, GrokNarrativeBrief
from ..grok.models import GrokSearchAnswer
from ..identity import utc_datetime
from .active_trigger import ActiveNarrativeTrigger
from .investigation_inputs import NarrativeEvent
from .telegram_trigger import TelegramNarrativeTrigger


def active_trigger_payload(trigger: ActiveNarrativeTrigger) -> dict[str, object]:
    return {
        "tweet_id": trigger.tweet_id,
        "actor_handle": trigger.actor_handle,
        "text": trigger.text,
        "text_sha256": sha256(trigger.text.encode("utf-8")).hexdigest(),
        "event_at": utc_datetime(trigger.event_at).isoformat(),
        "status_url": trigger.status_url,
        "post_type": trigger.post_type,
    }


def telegram_trigger_payload(
    trigger: TelegramNarrativeTrigger,
) -> dict[str, object]:
    return {
        "channel": trigger.channel,
        "message_id": trigger.message_id,
        "text": trigger.text,
        "text_sha256": sha256(trigger.text.encode("utf-8")).hexdigest(),
        "event_at": utc_datetime(trigger.event_at).isoformat(),
        "message_url": trigger.message_url,
        "post_type": "telegram_channel_post",
    }


def answer_payload(answer: GrokSearchAnswer | None) -> dict[str, object] | None:
    if answer is None:
        return None
    return {
        "response_id": answer.response_id,
        "model": answer.model,
        "text": answer.text,
        "text_sha256": sha256(answer.text.encode("utf-8")).hexdigest(),
        "sources": [
            {"url": item.url, "title": item.title, "type": item.source_type}
            for item in answer.sources
        ],
        "citations": [
            {
                "url": item.url,
                "title": item.title,
                "start_index": item.start_index,
                "end_index": item.end_index,
            }
            for item in answer.citations
        ],
        "candidate_urls": list(answer.candidate_urls),
        "usage": dict(answer.usage),
    }


def _ca_payload(carrier: CaReference | None) -> dict[str, str] | None:
    if carrier is None:
        return None
    return {
        "chain": carrier.chain,
        "address": carrier.address,
        "symbol": carrier.symbol,
    }


def brief_payload(brief: GrokNarrativeBrief | None) -> dict[str, object] | None:
    if brief is None:
        return None
    return {
        "narrative_key": brief.narrative_key,
        "one_line_meme": brief.one_line_meme,
        "event_role": brief.event_role.value,
        "narrative_source_summary": brief.narrative_source_summary,
        "why_now": brief.why_now,
        "propagation_engine": list(brief.propagation_engine),
        "future_24h_path": list(brief.future_24h_path),
        "ca_carrier_status": brief.ca_carrier_status.value,
        "competing_cas": [_ca_payload(item) for item in brief.competing_cas],
        "narrative_leader": _ca_payload(brief.narrative_leader),
        "market_leader": _ca_payload(brief.market_leader),
        "phase": brief.phase.value,
        "catalyst_type": brief.catalyst_type.value,
        "counter_evidence": list(brief.counter_evidence),
        "invalidation_conditions": list(brief.invalidation_conditions),
        "unknowns": list(brief.unknowns),
    }


def event_payload(event: NarrativeEvent) -> dict[str, object]:
    return {
        "event_id": event.event_id,
        "kind": event.kind.value,
        "actor": event.actor.to_payload(),
        "action": event.action.value,
        "endorsement": event.endorsement.value,
        "receipt": event.receipt.to_payload(),
        "claim": event.claim,
        "first_seen_at": event.first_seen_at.isoformat(),
        "token_address": event.token_address,
        "exact_ca": event.exact_ca,
        "parent_ids": list(event.parent_ids),
    }
