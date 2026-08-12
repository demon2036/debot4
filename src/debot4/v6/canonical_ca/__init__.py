"""Competing-contract evidence matrix and conservative resolver."""

from .rules import (
    CaCandidate,
    CanonicalDecision,
    leader_change_event,
    resolve_canonical_ca,
)
from .monitor import CanonicalCaMonitor

__all__ = [
    "CaCandidate",
    "CanonicalCaMonitor",
    "CanonicalDecision",
    "leader_change_event",
    "resolve_canonical_ca",
]
