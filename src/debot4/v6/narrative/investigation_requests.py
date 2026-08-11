"""Explicit constructors for the two discovery entrances."""

from __future__ import annotations

from datetime import datetime

from .domain import TokenRef
from .investigation_domain import DiscoveryMode, PumpPhase
from .investigation_inputs import (
    CapitalContext,
    CarrierCandidate,
    InvestigationRequest,
    NarrativeEvent,
)


def active_investigation_request(
    *,
    trigger_id: str,
    trigger_event_id: str,
    narrative_key: str,
    as_of: datetime,
    events: tuple[NarrativeEvent, ...],
    carriers: tuple[CarrierCandidate, ...],
    capital: CapitalContext = CapitalContext(),
    pump_phase: PumpPhase = PumpPhase.UNKNOWN,
    invalidation_conditions: tuple[str, ...] = (),
) -> InvestigationRequest:
    """Start from a monitored actor event, then map the correct carrier."""

    return InvestigationRequest(
        mode=DiscoveryMode.ACTIVE_ACTOR,
        trigger_id=trigger_id,
        trigger_event_id=trigger_event_id,
        trigger_token=None,
        narrative_key=narrative_key,
        as_of=as_of,
        events=events,
        carriers=carriers,
        capital=capital,
        pump_phase=pump_phase,
        invalidation_conditions=invalidation_conditions,
    )


def passive_investigation_request(
    *,
    trigger_id: str,
    trigger_token: TokenRef,
    narrative_key: str,
    as_of: datetime,
    events: tuple[NarrativeEvent, ...],
    carriers: tuple[CarrierCandidate, ...],
    capital: CapitalContext,
    pump_phase: PumpPhase = PumpPhase.UNKNOWN,
    invalidation_conditions: tuple[str, ...] = (),
) -> InvestigationRequest:
    """Start from a DeBot token, then prove its story and carrier identity."""

    return InvestigationRequest(
        mode=DiscoveryMode.PASSIVE_DEBOT,
        trigger_id=trigger_id,
        trigger_event_id=None,
        trigger_token=trigger_token,
        narrative_key=narrative_key,
        as_of=as_of,
        events=events,
        carriers=carriers,
        capital=capital,
        pump_phase=pump_phase,
        invalidation_conditions=invalidation_conditions,
    )
