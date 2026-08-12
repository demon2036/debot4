"""Pure role-aware queue values for X accounts discovered from market evidence."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class XAccountRole(str, Enum):
    KOL_CANDIDATE = "kol_candidate"
    SCANNER = "scanner"
    PROJECT = "project"
    COORDINATED_PROMOTION = "coordinated_promotion"
    CATALYST = "catalyst"
    RESEARCH = "research"
    UNREVIEWED = "unreviewed"


EXCLUDED_X_ACCOUNT_ROLES = frozenset({
    XAccountRole.SCANNER,
    XAccountRole.PROJECT,
    XAccountRole.COORDINATED_PROMOTION,
})


def is_excluded_x_account_role(role: XAccountRole | str | None) -> bool:
    """Return whether a reviewed role cannot be treated as an independent call."""

    if role is None:
        return False
    try:
        normalized = role if isinstance(role, XAccountRole) else XAccountRole(role)
    except ValueError:
        return False
    return normalized in EXCLUDED_X_ACCOUNT_ROLES


@dataclass(frozen=True, slots=True)
class XAccountEvidence:
    handle: str
    stable_user_id: str
    display_name: str
    source_kinds: tuple[str, ...]
    eligible_token_count: int
    pre_peak_post_token_count: int
    wallet_binding_pass: bool
    provider_high_frequency: bool

    def __post_init__(self) -> None:
        if min(self.eligible_token_count, self.pre_peak_post_token_count) < 0:
            raise ValueError("account evidence counts cannot be negative")
        if self.pre_peak_post_token_count > self.eligible_token_count:
            raise ValueError("pre-peak post count cannot exceed eligible-token count")
        object.__setattr__(self, "handle", self.handle.strip().lstrip("@"))
        object.__setattr__(self, "source_kinds", tuple(sorted(set(self.source_kinds))))


@dataclass(frozen=True, slots=True)
class XAccountQueueAssessment:
    role: XAccountRole
    monitor_candidate: bool
    smart_wallet_candidate: bool
    reasons: tuple[str, ...]


def assess_x_account_queue(
    evidence: XAccountEvidence, *, reviewed_role: XAccountRole | None = None,
) -> XAccountQueueAssessment:
    """Keep account discovery separate from KOL and smart-wallet qualification."""

    role = reviewed_role or XAccountRole.UNREVIEWED
    if is_excluded_x_account_role(role):
        return XAccountQueueAssessment(
            role, False, False, (f"reviewed_{role.value}",),
        )
    reviewed_signal = role in {
        XAccountRole.KOL_CANDIDATE,
        XAccountRole.CATALYST,
        XAccountRole.RESEARCH,
    }
    signal_evidence = bool(
        evidence.pre_peak_post_token_count
        or evidence.wallet_binding_pass
        or reviewed_signal
    )
    identity_complete = bool(evidence.stable_user_id and evidence.source_kinds)
    monitor = identity_complete and signal_evidence
    reasons = ["stable_x_identity" if identity_complete else "x_identity_incomplete"]
    if reviewed_signal:
        reasons.append(f"reviewed_{role.value}")
    if evidence.wallet_binding_pass:
        reasons.append("provider_wallet_x_binding")
    if evidence.pre_peak_post_token_count:
        reasons.append("has_pre_peak_exact_ca_post")
    if identity_complete and not signal_evidence:
        reasons.append("insufficient_monitor_evidence")
    if evidence.provider_high_frequency:
        reasons.append("high_frequency_excluded_from_wallet_signal")
    smart = False  # Full period activity and token outcomes are mandatory elsewhere.
    return XAccountQueueAssessment(role, monitor, smart, tuple(reasons))
