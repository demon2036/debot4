"""Pure evidence values for wallets publicly claimed on an X profile."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re
from typing import Mapping

from .models import normalize_evm_address


_HANDLE = re.compile(r"[A-Za-z0-9_]{1,15}")
_USER_ID = re.compile(r"[1-9][0-9]{5,24}")


class XWalletClaimVerdict(str, Enum):
    SELF_DISCLOSED = "SELF_DISCLOSED"
    PROVIDER_CORROBORATED = "PROVIDER_CORROBORATED"


@dataclass(frozen=True, slots=True)
class XProfileWalletClaim:
    handle: str
    stable_user_id: str
    wallet: str
    profile_url: str
    profile_payload_sha256: str
    provider_handles: tuple[str, ...] = ()
    provider_bound: bool | None = None

    def __post_init__(self) -> None:
        handle = self.handle.strip().lstrip("@")
        if not _HANDLE.fullmatch(handle) or not _USER_ID.fullmatch(self.stable_user_id):
            raise ValueError("wallet claim needs a stable X identity")
        if self.profile_url != f"https://api.fxtwitter.com/{handle}":
            raise ValueError("wallet claim needs the directly fetched X profile")
        if not re.fullmatch(r"[0-9a-f]{64}", self.profile_payload_sha256):
            raise ValueError("wallet claim needs an X profile fingerprint")
        handles = tuple(dict.fromkeys(
            item.strip().lstrip("@").casefold()
            for item in self.provider_handles if item.strip()
        ))
        if any(not _HANDLE.fullmatch(item) for item in handles):
            raise ValueError("provider wallet handles are invalid")
        object.__setattr__(self, "handle", handle)
        object.__setattr__(self, "wallet", normalize_evm_address(self.wallet))
        object.__setattr__(self, "provider_handles", handles)

    @property
    def verdict(self) -> XWalletClaimVerdict:
        expected = self.handle.casefold()
        if self.provider_bound is True and self.provider_handles == (expected,):
            return XWalletClaimVerdict.PROVIDER_CORROBORATED
        return XWalletClaimVerdict.SELF_DISCLOSED

    @property
    def usable_as_provider_wallet_x_binding(self) -> bool:
        return self.verdict is XWalletClaimVerdict.PROVIDER_CORROBORATED


def corroborated_claim_from_mapping(
    row: Mapping[str, object],
) -> XProfileWalletClaim | None:
    """Validate a persisted public claim before using it as a wallet/X binding."""

    handles = row.get("provider_handles")
    if not isinstance(handles, list):
        raise ValueError("persisted wallet claim provider handles must be a list")
    claim = XProfileWalletClaim(
        handle=str(row.get("handle") or ""),
        stable_user_id=str(row.get("stable_user_id") or ""),
        wallet=str(row.get("wallet") or ""),
        profile_url=str(row.get("profile_url") or ""),
        profile_payload_sha256=str(row.get("profile_payload_sha256") or ""),
        provider_handles=tuple(str(item) for item in handles),
        provider_bound=row.get("provider_bound")
        if isinstance(row.get("provider_bound"), bool) else None,
    )
    persisted = str(row.get("verdict") or "")
    if persisted != claim.verdict.value:
        raise ValueError("persisted wallet claim verdict disagrees with evidence")
    return claim if claim.usable_as_provider_wallet_x_binding else None
