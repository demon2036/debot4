"""Fail-closed passive narrative search triggered by a DeBot signal."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from ..domain import DeBotSignal
from ..grok.client import Grok2ApiClient
from ..grok.briefs import GrokNarrativeBrief
from ..grok.models import GrokSearchAnswer
from ..grok.prompts import SYSTEM, passive_investigation_prompt
from ..grok.structured import search_narrative_brief
from ..identity import bsc_address, stable_id, utc_datetime
from .passive_evidence import passive_answer_audit
from .passive_hints import verify_trigger_hints
from .passive_trigger_values import (
    bounded_social_urls,
    describe_signal_anomaly,
    optional_text,
)

if TYPE_CHECKING:
    from ..grok.leads import GrokXLead
    from .investigation_inputs import NarrativeEvent
    from .trusted_ingest import XStatusVerifier


PASSIVE_TRIGGER_SCHEMA = "debot.v6.passive_narrative_trigger.v1"
PASSIVE_RESULT_SCHEMA = "debot.v6.passive_narrative_search.v1"


class PassiveNarrativeStatus(str, Enum):
    EVIDENCE_FOUND = "EVIDENCE_FOUND"
    WAIT = "WAIT"


@dataclass(frozen=True, slots=True)
class PassiveNarrativeTrigger:
    """Auditable market-first request; its social URLs remain untrusted hints."""

    exact_ca: str
    signal_id: str
    observed_at: datetime
    token_name: str | None
    token_symbol: str | None
    anomaly: str
    social_urls: tuple[str, ...] = ()
    trigger_id: str = field(init=False)

    def __post_init__(self) -> None:
        exact_ca = bsc_address(self.exact_ca)
        signal_id = self.signal_id.strip()
        observed_at = utc_datetime(self.observed_at)
        token_name = optional_text(self.token_name, 160)
        token_symbol = optional_text(self.token_symbol, 80)
        anomaly = self.anomaly.strip()
        social_urls = bounded_social_urls(self.social_urls)
        if not signal_id or len(signal_id) > 128:
            raise ValueError("signal_id is required and must be at most 128 characters")
        if not anomaly or len(anomaly) > 4_000:
            raise ValueError("anomaly is required and must be at most 4000 characters")
        object.__setattr__(self, "exact_ca", exact_ca)
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "observed_at", observed_at)
        object.__setattr__(self, "token_name", token_name)
        object.__setattr__(self, "token_symbol", token_symbol)
        object.__setattr__(self, "anomaly", anomaly)
        object.__setattr__(self, "social_urls", social_urls)
        object.__setattr__(
            self,
            "trigger_id",
            stable_id(
                "passive-narrative",
                PASSIVE_TRIGGER_SCHEMA,
                exact_ca,
                signal_id,
                observed_at.isoformat(),
                token_name or "",
                token_symbol or "",
                anomaly,
                *social_urls,
            ),
        )

    @classmethod
    def from_signal(
        cls, signal: DeBotSignal, *, anomaly: str | None = None
    ) -> "PassiveNarrativeTrigger":
        return cls(
            exact_ca=signal.token_address,
            signal_id=signal.signal_id,
            observed_at=signal.available_at,
            token_name=signal.token_name,
            token_symbol=signal.token_symbol,
            anomaly=anomaly or describe_signal_anomaly(signal),
            social_urls=signal.narrative_urls,
        )

    def search_context(self) -> str:
        lines = [
            self.anomaly,
            f"trigger reference: {self.signal_id}",
            f"token name: {self.token_name or 'unknown'}",
            f"token symbol: {self.token_symbol or 'unknown'}",
        ]
        if self.social_urls:
            lines.append("已有社交 URL（仅作未核验搜索线索）:")
            lines.extend(f"- {url}" for url in self.social_urls)
        return "\n".join(lines)

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": PASSIVE_TRIGGER_SCHEMA,
            "trigger_id": self.trigger_id,
            "exact_ca": self.exact_ca,
            "signal_id": self.signal_id,
            "observed_at": self.observed_at.isoformat(),
            "token_name": self.token_name,
            "token_symbol": self.token_symbol,
            "anomaly": self.anomaly,
            "social_urls": list(self.social_urls),
            "social_urls_are_evidence": False,
        }


@dataclass(frozen=True, slots=True)
class PassiveNarrativeResult:
    """Discovery output only; it never represents evidence or trade authority."""

    status: PassiveNarrativeStatus
    reason: str
    trigger: PassiveNarrativeTrigger
    answer: GrokSearchAnswer | None
    brief: GrokNarrativeBrief | None = None
    x_status_leads: tuple[GrokXLead, ...] = ()
    events: tuple[NarrativeEvent, ...] = ()
    verified_urls: tuple[str, ...] = ()
    failed_urls: tuple[str, ...] = ()
    repair_answer: GrokSearchAnswer | None = None

    def __post_init__(self) -> None:
        status = PassiveNarrativeStatus(self.status)
        reason = self.reason.strip()
        leads = tuple(self.x_status_leads)
        events = tuple(self.events)
        if not reason:
            raise ValueError("passive narrative result reason is required")
        if status is PassiveNarrativeStatus.EVIDENCE_FOUND and (
            self.answer is None or self.brief is None or not events
        ):
            raise ValueError("EVIDENCE_FOUND requires verified narrative events")
        if status is PassiveNarrativeStatus.WAIT and events:
            raise ValueError("WAIT cannot expose verified narrative events")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "x_status_leads", leads)
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "verified_urls", tuple(self.verified_urls))
        object.__setattr__(self, "failed_urls", tuple(self.failed_urls))

    @property
    def authorizes_trade(self) -> bool:
        return False

    def to_payload(self) -> dict[str, object]:
        return {
            "schema": PASSIVE_RESULT_SCHEMA,
            "status": self.status.value,
            "reason": self.reason,
            "authorizes_trade": False,
            "contains_verified_events": bool(self.events),
            "trigger": self.trigger.to_payload(),
            "answer": passive_answer_audit(self.answer),
            "brief": None if self.brief is None else {
                "narrative_key": self.brief.narrative_key,
                "one_line_meme": self.brief.one_line_meme,
                "event_role": self.brief.event_role.value,
                "why_now": self.brief.why_now,
                "unknowns": list(self.brief.unknowns),
            },
            "x_status_leads": [
                {
                    "response_id": lead.response_id,
                    "handle": lead.handle,
                    "status_id": lead.status_id,
                    "candidate_url": lead.candidate_url,
                    "canonical_url": lead.canonical_url,
                }
                for lead in self.x_status_leads
            ],
            "verified_urls": list(self.verified_urls),
            "failed_urls": list(self.failed_urls),
            "verified_event_ids": [item.event_id for item in self.events],
        }


def investigate_passive_signal(
    signal: DeBotSignal,
    client: Grok2ApiClient,
    verifier: XStatusVerifier,
    *,
    anomaly: str | None = None,
) -> PassiveNarrativeResult:
    """Create the audit trigger and run one fail-closed Grok search."""

    trigger = PassiveNarrativeTrigger.from_signal(signal, anomaly=anomaly)
    return investigate_passive_trigger(trigger, client, verifier)


def investigate_passive_trigger(
    trigger: PassiveNarrativeTrigger,
    client: Grok2ApiClient,
    verifier: XStatusVerifier,
) -> PassiveNarrativeResult:
    hints = verify_trigger_hints(trigger.social_urls, verifier)
    context = trigger.search_context()
    verified_context = hints.prompt_context()
    if verified_context:
        context = f"{context}\n\n{verified_context}"
    prompt = passive_investigation_prompt(
        token_address=trigger.exact_ca,
        anomaly=context,
        observed_at=trigger.observed_at,
    )
    searched = search_narrative_brief(client, prompt, instructions=SYSTEM)
    if not searched.ok:
        return PassiveNarrativeResult(
            PassiveNarrativeStatus.WAIT,
            searched.error,
            trigger,
            searched.answer,
            repair_answer=searched.repair_answer,
        )
    answer = searched.answer
    brief = searched.brief
    assert answer is not None and brief is not None
    from .passive_evidence import verify_passive_evidence

    evidence = verify_passive_evidence(
        answer, brief, verifier, seed_statuses=hints.statuses
    )
    failed_urls = tuple(dict.fromkeys(
        (*hints.failed_urls, *evidence.failed_urls)
    ))
    if not evidence.events:
        return PassiveNarrativeResult(
            PassiveNarrativeStatus.WAIT,
            "no_verified_narrative_evidence",
            trigger,
            answer,
            brief,
            evidence.leads,
            (),
            evidence.verified_urls,
            failed_urls,
            searched.repair_answer,
        )
    exact_ca = trigger.exact_ca
    bound = any(item.token_address == exact_ca for item in evidence.events)
    if not bound:
        return PassiveNarrativeResult(
            PassiveNarrativeStatus.WAIT,
            "verified_narrative_found_trigger_ca_unbound",
            trigger,
            answer,
            brief,
            evidence.leads,
            (),
            evidence.verified_urls,
            failed_urls,
            searched.repair_answer,
        )
    return PassiveNarrativeResult(
        PassiveNarrativeStatus.EVIDENCE_FOUND,
        "verified_narrative_evidence_found",
        trigger,
        answer,
        brief,
        evidence.leads,
        evidence.events,
        evidence.verified_urls,
        failed_urls,
        searched.repair_answer,
    )
