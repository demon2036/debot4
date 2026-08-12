"""Pure evidence grades for X posts intersecting audited KOL buys."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class XSignalGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    EXCLUDE = "EXCLUDE"


@dataclass(frozen=True, slots=True)
class XSignalEvidence:
    stable_x_identity: bool
    pre_peak_exact_ca_post: bool
    rpc_clean_kol_buy_count: int
    exact_author_wallet_buy_before_post_count: int
    wallet_x_binding: bool
    excluded_role: bool = False

    def __post_init__(self) -> None:
        if min(
            self.rpc_clean_kol_buy_count,
            self.exact_author_wallet_buy_before_post_count,
        ) < 0:
            raise ValueError("X signal evidence counts cannot be negative")
        if (
            self.exact_author_wallet_buy_before_post_count
            and not self.wallet_x_binding
        ):
            raise ValueError("author-wallet buy needs an exact wallet/X binding")


@dataclass(frozen=True, slots=True)
class XSignalAssessment:
    grade: XSignalGrade
    reasons: tuple[str, ...]
    structural_candidate: bool


def assess_x_signal(evidence: XSignalEvidence) -> XSignalAssessment:
    """Grade evidence axes without interpreting the author's post meaning."""

    if evidence.excluded_role:
        return XSignalAssessment(
            XSignalGrade.EXCLUDE, ("non_independent_account_role",), False,
        )
    if not evidence.stable_x_identity:
        return XSignalAssessment(
            XSignalGrade.EXCLUDE, ("stable_x_identity_missing",), False,
        )
    if (
        evidence.pre_peak_exact_ca_post
        and evidence.exact_author_wallet_buy_before_post_count > 0
    ):
        return XSignalAssessment(XSignalGrade.A, (
            "pre_peak_exact_ca_post",
            "same_author_bound_wallet_bought_exact_ca_before_post",
        ), True)
    if evidence.pre_peak_exact_ca_post and evidence.rpc_clean_kol_buy_count > 0:
        return XSignalAssessment(XSignalGrade.B, (
            "pre_peak_exact_ca_post",
            "token_has_independent_rpc_verified_kol_buy",
        ), True)
    if evidence.pre_peak_exact_ca_post:
        return XSignalAssessment(
            XSignalGrade.C, ("pre_peak_exact_ca_post_only",), True,
        )
    if evidence.wallet_x_binding:
        return XSignalAssessment(
            XSignalGrade.D, ("wallet_x_binding_without_pre_peak_exact_ca_post",), False,
        )
    return XSignalAssessment(
        XSignalGrade.EXCLUDE, ("insufficient_signal_evidence",), False,
    )
