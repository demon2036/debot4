"""Competing-contract evidence matrix and conservative resolver."""

from .rules import (
    CaCandidate,
    CanonicalDecision,
    leader_change_event,
    resolve_canonical_ca,
)

__all__ = [
    "CaCandidate",
    "CanonicalDecision",
    "leader_change_event",
    "resolve_canonical_ca",
]
