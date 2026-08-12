"""Optional attribution joining a GMGN trade, wallet profile and public X profile."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import normalize_evm_address


class XBindingVerdict(str, Enum):
    PASS = "PASS"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class WalletXIdentity:
    wallet: str
    provider_activity_handle: str | None
    public_profile_handle: str | None
    stat_profile_handle: str | None
    provider_bound: bool | None
    fxtwitter_handle: str | None
    fxtwitter_user_id: str | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "wallet", normalize_evm_address(self.wallet))


@dataclass(frozen=True, slots=True)
class XBindingAssessment:
    verdict: XBindingVerdict
    canonical_handle: str | None
    stable_user_id: str | None
    reasons: tuple[str, ...]


def assess_x_binding(identity: WalletXIdentity) -> XBindingAssessment:
    """Assess an X attribution claim without deciding wallet or token eligibility."""

    handles = tuple(_handle(item) for item in (
        identity.provider_activity_handle,
        identity.public_profile_handle,
        identity.stat_profile_handle,
    ))
    if any(item is None for item in handles):
        return XBindingAssessment(
            XBindingVerdict.WAIT, None, None, ("provider_x_identity_incomplete",),
        )
    if len(set(handles)) != 1:
        return XBindingAssessment(
            XBindingVerdict.REJECT, None, None, ("provider_x_handles_conflict",),
        )
    canonical = handles[0]
    if identity.provider_bound is not True:
        return XBindingAssessment(
            XBindingVerdict.WAIT, canonical, None, ("provider_x_binding_unconfirmed",),
        )
    observed = _handle(identity.fxtwitter_handle)
    if observed is None or not identity.fxtwitter_user_id:
        return XBindingAssessment(
            XBindingVerdict.WAIT, canonical, None, ("fxtwitter_profile_unverified",),
        )
    if observed != canonical:
        return XBindingAssessment(
            XBindingVerdict.REJECT, canonical, identity.fxtwitter_user_id,
            ("fxtwitter_handle_conflict",),
        )
    return XBindingAssessment(
        XBindingVerdict.PASS, canonical, identity.fxtwitter_user_id,
        ("wallet_provider_profile_and_x_identity_agree",),
    )


def _handle(value: str | None) -> str | None:
    handle = str(value or "").strip().lstrip("@").casefold()
    return handle or None
