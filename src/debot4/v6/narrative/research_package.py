"""Content-addressed audit packages emitted by the v6 narrative runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from hashlib import sha256
from types import MappingProxyType
from typing import Any, Mapping

from ..identity import canonical_json, json_safe, stable_id, utc_datetime
from .active_trigger import ActiveNarrativeResult, ActiveNarrativeTrigger
from .passive_trigger import PassiveNarrativeResult
from .research_serializers import (
    active_trigger_payload,
    answer_payload,
    brief_payload,
    event_payload,
    telegram_trigger_payload,
)
from .telegram_trigger import TelegramNarrativeResult


RESEARCH_PACKAGE_SCHEMA = "debot.v6.narrative_research_package.v1"


class ResearchMode(str, Enum):
    ACTIVE_ACTOR = "ACTIVE_ACTOR"
    ACTIVE_TELEGRAM = "ACTIVE_TELEGRAM"
    PASSIVE_DEBOT = "PASSIVE_DEBOT"
    PASSIVE_MARKET = "PASSIVE_MARKET"
    PASSIVE_CATALYST_MINT = "PASSIVE_CATALYST_MINT"


@dataclass(frozen=True, slots=True)
class NarrativeResearchPackage:
    """Immutable research output; its schema has no execution directive."""

    mode: ResearchMode
    trigger_id: str
    triggered_at: datetime
    researched_at: datetime
    status: str
    reason: str
    research: Mapping[str, Any]
    package_id: str = field(init=False)
    content_sha256: str = field(init=False)
    authorizes_trade: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        mode = ResearchMode(self.mode)
        trigger_id = self.trigger_id.strip()
        status = self.status.strip()
        reason = self.reason.strip()
        triggered = utc_datetime(self.triggered_at)
        researched = utc_datetime(self.researched_at)
        if not trigger_id or len(trigger_id) > 256:
            raise ValueError("research trigger_id is required and bounded")
        if not status or not reason or len(status) > 80 or len(reason) > 1_000:
            raise ValueError("research status and reason are required and bounded")
        if researched < triggered:
            raise ValueError("research cannot predate its trigger")
        safe = json_safe(self.research)
        if not isinstance(safe, dict):
            raise ValueError("research payload must be a mapping")
        _reject_trade_authority(safe)
        frozen = _freeze(safe)
        identity = _identity_payload(
            mode, trigger_id, triggered, researched, status, reason, safe
        )
        digest = sha256(canonical_json(identity).encode("utf-8")).hexdigest()
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "trigger_id", trigger_id)
        object.__setattr__(self, "triggered_at", triggered)
        object.__setattr__(self, "researched_at", researched)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "research", frozen)
        object.__setattr__(self, "content_sha256", digest)
        object.__setattr__(
            self, "package_id", stable_id("narrative-research", digest)
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema": RESEARCH_PACKAGE_SCHEMA,
            "package_id": self.package_id,
            "content_sha256": self.content_sha256,
            **_identity_payload(
                self.mode,
                self.trigger_id,
                self.triggered_at,
                self.researched_at,
                self.status,
                self.reason,
                json_safe(self.research),
            ),
            "research_only": True,
            "authorizes_trade": False,
            "execution_directive": None,
        }


def package_active_result(
    result: ActiveNarrativeResult, researched_at: datetime
) -> NarrativeResearchPackage:
    trigger = result.trigger
    trigger_id = stable_id(
        "active-narrative", trigger.actor_handle.casefold(), trigger.tweet_id,
        trigger.status_url,
    )
    research = {
        "trigger": active_trigger_payload(trigger),
        "result": {
            "status": result.status.value,
            "reason": result.reason,
            "answer": answer_payload(result.answer),
            "format_retry_answer": answer_payload(result.repair_answer),
            "brief": brief_payload(result.brief),
            "events": [event_payload(item) for item in result.events],
            "verified_urls": list(result.verified_urls),
            "failed_urls": list(result.failed_urls),
            "authorizes_trade": False,
        },
        "grok_answer_is_evidence": False,
    }
    return NarrativeResearchPackage(
        ResearchMode.ACTIVE_ACTOR,
        trigger_id,
        utc_datetime(trigger.event_at),
        researched_at,
        result.status.value,
        result.reason,
        research,
    )


def package_active_failure(
    trigger: ActiveNarrativeTrigger, researched_at: datetime, error_type: str
) -> NarrativeResearchPackage:
    reason = f"runtime_research_failed:{error_type.strip() or 'Exception'}"
    result = {
        "trigger": active_trigger_payload(trigger),
        "result": {"status": "WAIT", "reason": reason, "authorizes_trade": False},
        "grok_answer_is_evidence": False,
    }
    trigger_id = stable_id(
        "active-narrative", trigger.actor_handle.casefold(), trigger.tweet_id,
        trigger.status_url,
    )
    return NarrativeResearchPackage(
        ResearchMode.ACTIVE_ACTOR,
        trigger_id,
        utc_datetime(trigger.event_at),
        researched_at,
        "WAIT",
        reason,
        result,
    )


def package_telegram_result(
    result: TelegramNarrativeResult, researched_at: datetime
) -> NarrativeResearchPackage:
    trigger = result.trigger
    trigger_id = stable_id(
        "telegram-narrative", trigger.channel, str(trigger.message_id)
    )
    research = {
        "trigger": telegram_trigger_payload(trigger),
        "result": {
            "status": result.status.value,
            "reason": result.reason,
            "answer": answer_payload(result.answer),
            "format_retry_answer": answer_payload(result.repair_answer),
            "brief": brief_payload(result.brief),
            "events": [event_payload(item) for item in result.events],
            "verified_urls": list(result.verified_urls),
            "failed_urls": list(result.failed_urls),
            "authorizes_trade": False,
        },
        "grok_answer_is_evidence": False,
    }
    return NarrativeResearchPackage(
        ResearchMode.ACTIVE_TELEGRAM,
        trigger_id,
        utc_datetime(trigger.event_at),
        researched_at,
        result.status.value,
        result.reason,
        research,
    )


def package_passive_result(
    result: PassiveNarrativeResult,
    researched_at: datetime,
    *,
    mode: ResearchMode = ResearchMode.PASSIVE_DEBOT,
) -> NarrativeResearchPackage:
    if mode not in (
        ResearchMode.PASSIVE_DEBOT,
        ResearchMode.PASSIVE_MARKET,
        ResearchMode.PASSIVE_CATALYST_MINT,
    ):
        raise ValueError("passive package requires a passive research mode")
    leads = [
        {
            "response_id": item.response_id,
            "handle": item.handle,
            "status_id": item.status_id,
            "candidate_url": item.candidate_url,
            "canonical_url": item.canonical_url,
        }
        for item in result.x_status_leads
    ]
    research = {
        "trigger": result.trigger.to_payload(),
        "result": {
            "status": result.status.value,
            "reason": result.reason,
            "answer": answer_payload(result.answer),
            "format_retry_answer": answer_payload(result.repair_answer),
            "brief": brief_payload(result.brief),
            "x_status_leads": leads,
            "events": [event_payload(item) for item in result.events],
            "verified_urls": list(result.verified_urls),
            "failed_urls": list(result.failed_urls),
            "authorizes_trade": False,
        },
        "x_status_leads_are_evidence": False,
        "grok_answer_is_evidence": False,
    }
    return NarrativeResearchPackage(
        mode,
        result.trigger.trigger_id,
        result.trigger.observed_at,
        researched_at,
        result.status.value,
        result.reason,
        research,
    )


def _identity_payload(
    mode: ResearchMode,
    trigger_id: str,
    triggered_at: datetime,
    researched_at: datetime,
    status: str,
    reason: str,
    research: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "mode": mode.value,
        "trigger_id": trigger_id,
        "triggered_at": triggered_at.isoformat(),
        "researched_at": researched_at.isoformat(),
        "status": status,
        "reason": reason,
        "research": research,
    }


def _reject_trade_authority(value: object) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() == "authorizes_trade" and item is not False:
                raise ValueError("research package cannot authorize a trade")
            _reject_trade_authority(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_trade_authority(item)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value
