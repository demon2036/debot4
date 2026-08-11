"""Canonical hashes for v6 narrative evidence and decisions."""

from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .dossier import NarrativeDossier
from .valuation import ValuationView


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def stable_identity(namespace: str, value: Any) -> tuple[str, str]:
    digest = canonical_sha256(value)
    return f"{namespace}:{digest}", digest


def dossier_hash(dossier: NarrativeDossier) -> str:
    return canonical_sha256(dossier_payload(dossier))


def dossier_payload(dossier: NarrativeDossier) -> dict[str, object]:
    evidence = sorted(dossier.evidence, key=lambda item: item.evidence_id)
    findings = sorted(dossier.findings, key=lambda item: item.dimension.value)
    return {
        "token": {"chain": dossier.token.chain, "address": dossier.token.address},
        "as_of": dossier.as_of.isoformat(),
        "thesis": dossier.thesis,
        "canonicality": dossier.canonicality.value,
        "stage": dossier.stage.value,
        "alternative_theses": list(dossier.alternative_theses),
        "fatal_unknowns": list(dossier.fatal_unknowns),
        "evidence": [
            {
                "evidence_id": item.evidence_id,
                "source": item.source.value,
                "role": item.role.value,
                "claim": item.claim,
                "published_at": item.published_at.isoformat(),
                "first_seen_at": item.first_seen_at.isoformat(),
                "captured_at": item.captured_at.isoformat(),
                "token_address": item.token_address,
                "source_actor": item.source_actor,
                "status_id": item.status_id,
                "exact_ca": item.exact_ca,
                "independence_group": item.independence_group,
                "scope": item.scope.value,
            }
            for item in evidence
        ],
        "findings": [
            {
                "dimension": item.dimension.value,
                "state": item.state.value,
                "finding": item.finding,
                "supports": list(item.supports),
                "contradicts": list(item.contradicts),
                "unknowns": list(item.unknowns),
            }
            for item in findings
        ],
    }


def valuation_payload(valuation: ValuationView | None) -> dict[str, object] | None:
    if valuation is None:
        return None
    return {
        "as_of": valuation.as_of.isoformat(),
        "current_market_cap_usd": valuation.current_market_cap_usd,
        "status": valuation.status.value,
        "notes": list(valuation.notes),
        "comparables": [
            {
                "token": {"chain": item.token.chain, "address": item.token.address},
                "label": item.label,
                "market_cap_usd": item.market_cap_usd,
                "as_of": item.as_of.isoformat(),
                "similarities": list(item.similarities),
                "differences": list(item.differences),
            }
            for item in sorted(
                valuation.comparables,
                key=lambda item: (item.token.chain, item.token.address, item.label),
            )
        ],
        "scenarios": [
            {
                "name": item.name,
                "low_usd": item.low_usd,
                "high_usd": item.high_usd,
                "rationale": item.rationale,
            }
            for item in sorted(valuation.scenarios, key=lambda item: item.name)
        ],
    }
