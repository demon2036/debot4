"""Strictly prior DeBot KOL wallet-BUY or participation-proxy evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from typing import Iterable, Mapping

from .domain import (
    EvidenceRole,
    EvidenceScope,
    EvidenceSource,
    TokenRef,
)
from .evidence import EvidenceItem
from .history_contracts import (
    PARTICIPATION_PROXY,
    WALLET_BUY,
    ContractAssessment,
    assess_contract,
)
from .models import (
    CurrentSignalBoundary,
    DEBOT_KOL_SOURCE,
    DEBOT_RANKS_SOURCE,
    HistoricalKolFact,
    aware_utc,
)
from .results import HistoricalKolAssessment, HistoryItemAudit


def assess_historical_kol_buys(
    token: TokenRef,
    facts: Iterable[HistoricalKolFact],
    *,
    current_signal: CurrentSignalBoundary | None,
    decision_time: datetime,
) -> HistoricalKolAssessment:
    cutoff = aware_utc(decision_time, "decision_time")
    records = tuple(facts)
    duplicates = Counter(item.evidence_identity for item in records)
    accepted: list[tuple[EvidenceItem, str]] = []
    audit: list[HistoryItemAudit] = []
    for fact in records:
        metadata = _metadata(fact.metadata_json)
        contract = assess_contract(metadata, fact)
        reason = _reason(token, fact, duplicates, current_signal, cutoff, contract)
        audit.append(_audit(fact, metadata, contract, reason))
        if contract.accepted and reason == contract.reason:
            accepted.append((_evidence(fact, contract), str(contract.evidence_kind)))
    accepted.sort(key=lambda item: (item[0].published_at, item[0].evidence_id))
    audit.sort(key=lambda item: (item.event_time, item.evidence_identity))
    kinds = {kind for _, kind in accepted}
    qualification_kind = (
        WALLET_BUY if WALLET_BUY in kinds
        else PARTICIPATION_PROXY if PARTICIPATION_PROXY in kinds
        else None
    )
    return HistoricalKolAssessment(
        qualified=bool(accepted),
        reason=(
            "historical_kol_wallet_buy_qualified"
            if qualification_kind == WALLET_BUY
            else "historical_kol_participation_proxy_qualified"
            if qualification_kind == PARTICIPATION_PROXY
            else "historical_kol_evidence_missing"
        ),
        qualification_kind=qualification_kind,
        evidence=tuple(item for item, _ in accepted),
        audit=tuple(audit),
    )


def _reason(
    token: TokenRef,
    fact: HistoricalKolFact,
    duplicates: Counter[str],
    current: CurrentSignalBoundary | None,
    cutoff: datetime,
    contract: ContractAssessment,
) -> str:
    if current is None:
        return "current_signal_boundary_missing"
    if duplicates[fact.evidence_identity] != 1:
        return "duplicate_evidence_identity"
    required_source = (
        DEBOT_RANKS_SOURCE
        if contract.evidence_kind == PARTICIPATION_PROXY
        else DEBOT_KOL_SOURCE
    )
    if fact.token_address != token.address or fact.source != required_source:
        return "fact_provenance_mismatch"
    if not _chronology_valid(fact):
        return "fact_time_order_invalid"
    if max(fact.event_time, fact.available_at, fact.qualified_at, fact.inserted_at) > cutoff:
        return "fact_unavailable_at_decision"
    if fact.signal_id == current.signal_id:
        return "current_signal_excluded"
    if fact.event_time >= current.event_at:
        return "fact_not_earlier_than_current_event"
    if max(fact.available_at, fact.qualified_at, fact.inserted_at) >= current.available_at:
        return "fact_not_known_before_current_signal"
    if not contract.accepted:
        return contract.reason
    return contract.reason


def _chronology_valid(fact: HistoricalKolFact) -> bool:
    return (
        fact.event_time <= fact.available_at <= fact.qualified_at
        and fact.qualified_at <= fact.inserted_at
    )


def _metadata(raw: str) -> Mapping[str, object]:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, Mapping) else {}


def _evidence(fact: HistoricalKolFact, contract: ContractAssessment) -> EvidenceItem:
    proxy = contract.evidence_kind == PARTICIPATION_PROXY
    return EvidenceItem(
        evidence_id=fact.evidence_identity,
        source=EvidenceSource.DEBOT if proxy else EvidenceSource.KOL,
        role=EvidenceRole.CAPITAL_CONFIRMATION,
        claim=(
            "Historical KOL participation proxy from DeBot ranks; not a wallet-level BUY"
            if proxy
            else "Official DeBot UI asserted a windowed KOL BUY before the current signal"
        ),
        published_at=fact.event_time,
        first_seen_at=fact.available_at,
        captured_at=fact.inserted_at,
        token_address=fact.token_address,
        source_actor=str(contract.source_actor or "DeBot KOL"),
        status_id=fact.signal_id,
        exact_ca=True,
        independence_group=f"debot-kol:{fact.signal_id}",
        scope=EvidenceScope.LIVE_ELIGIBLE,
    )


def _audit(
    fact: HistoricalKolFact,
    metadata: Mapping[str, object],
    contract: ContractAssessment,
    reason: str,
) -> HistoryItemAudit:
    provider = contract.provider or {}
    value = lambda key: str(provider[key]) if provider.get(key) is not None else None
    return HistoryItemAudit(
        fact.evidence_identity, fact.signal_id,
        contract.accepted and reason == contract.reason, reason,
        fact.event_time, fact.available_at, fact.qualified_at, fact.inserted_at,
        value("status"), value("verification_level"),
        provider.get("chain_verified") if isinstance(provider.get("chain_verified"), bool) else None,
        value("provider_channel_id"),
        str(metadata["signal_group"]) if metadata.get("signal_group") is not None else None,
        contract.evidence_kind,
    )
