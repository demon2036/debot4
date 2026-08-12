"""Pure review boundary for interpreting an exact-CA X post."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class XPostSemantic(str, Enum):
    OWN_POSITION = "own_position"
    MARKET_THESIS = "market_thesis"
    MARKET_CONTEXT = "market_context"
    RECAP = "recap"
    RELAY = "relay"
    REPLY_MENTION = "reply_mention"
    NEGATIVE_WARNING = "negative_warning"
    PROJECT_ANNOUNCEMENT = "project_announcement"
    UNREVIEWED = "unreviewed"


FORWARD_SIGNAL_SEMANTICS = frozenset({
    XPostSemantic.OWN_POSITION,
    XPostSemantic.MARKET_THESIS,
})


@dataclass(frozen=True, slots=True)
class XPostInterpretation:
    semantic: XPostSemantic
    manually_reviewed: bool
    structural_signal_candidate: bool
    excluded_account_role: bool = False


@dataclass(frozen=True, slots=True)
class XPostSemanticAssessment:
    causal_research_candidate: bool
    reasons: tuple[str, ...]


def assess_x_post_semantic(
    interpretation: XPostInterpretation,
) -> XPostSemanticAssessment:
    """Require human-reviewed forward meaning in addition to timing/evidence."""

    if interpretation.excluded_account_role:
        return XPostSemanticAssessment(False, ("excluded_account_role",))
    if not interpretation.manually_reviewed:
        return XPostSemanticAssessment(False, ("post_semantic_unreviewed",))
    if interpretation.semantic not in FORWARD_SIGNAL_SEMANTICS:
        return XPostSemanticAssessment(False, (
            f"post_semantic_{interpretation.semantic.value}",
        ))
    if not interpretation.structural_signal_candidate:
        return XPostSemanticAssessment(False, (
            f"reviewed_{interpretation.semantic.value}",
            "insufficient_structural_signal_evidence",
        ))
    return XPostSemanticAssessment(True, (
        f"reviewed_{interpretation.semantic.value}",
        "pre_peak_exact_ca_with_kol_buy_evidence",
    ))
