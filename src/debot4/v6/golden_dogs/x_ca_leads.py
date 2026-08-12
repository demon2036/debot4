"""Pure exact-CA joins for independently verified X status leads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Mapping

from .models import Observation


_EVM_CA = re.compile(r"(?<![0-9A-Fa-f])0x[0-9A-Fa-f]{40}(?![0-9A-Fa-f])")


@dataclass(frozen=True, slots=True)
class VerifiedXCaLead:
    handle: str
    stable_user_id: str
    status_url: str
    published_at: datetime
    address: str
    text: str
    status_payload_sha256: str
    profile_payload_sha256: str

    def __post_init__(self) -> None:
        published = self.published_at
        if published.tzinfo is None or published.utcoffset() is None:
            raise ValueError("X CA lead time must be timezone-aware")
        if self.address not in exact_evm_addresses(self.text):
            raise ValueError("X CA lead address must occur in verified text")
        object.__setattr__(self, "handle", self.handle.casefold())
        object.__setattr__(self, "published_at", published.astimezone(timezone.utc))
        object.__setattr__(self, "address", self.address.casefold())


@dataclass(frozen=True, slots=True)
class XMarketJoin:
    lead: VerifiedXCaLead
    observation: Observation
    timing: str


def exact_evm_addresses(text: str) -> tuple[str, ...]:
    """Extract boundary-safe exact EVM addresses without deciding their role."""

    return tuple(dict.fromkeys(match.group(0).casefold() for match in _EVM_CA.finditer(text)))


def verified_leads_from_row(row: Mapping[str, object]) -> tuple[VerifiedXCaLead, ...]:
    """Accept only stable-ID-authored status rows with both payload fingerprints."""

    if row.get("status") != "verified":
        return ()
    text = str(row.get("text") or "")
    published = _timestamp(str(row.get("published_at") or ""))
    common = {
        "handle": str(row.get("observed_handle") or ""),
        "stable_user_id": str(row.get("observed_author_id") or ""),
        "status_url": str(row.get("canonical_url") or ""),
        "published_at": published,
        "text": text,
        "status_payload_sha256": str(row.get("status_payload_sha256") or ""),
        "profile_payload_sha256": str(row.get("profile_payload_sha256") or ""),
    }
    if not all(common.values()) or common["stable_user_id"] != str(row.get("profile_user_id")):
        return ()
    return tuple(VerifiedXCaLead(address=address, **common) for address in exact_evm_addresses(text))


def join_verified_x_to_markets(
    leads: tuple[VerifiedXCaLead, ...],
    markets: Mapping[tuple[str, str], Observation],
) -> tuple[XMarketJoin, ...]:
    """Join exact CA to eligible markets; classify post time independently."""

    output = []
    for lead in leads:
        matches = tuple(
            item for (chain, address), item in markets.items()
            if address == lead.address and chain in {"bsc", "robinhood"}
        )
        for observation in matches:
            posted_at = int(lead.published_at.timestamp())
            if posted_at < observation.created_at:
                timing = "pre_creation"
            elif observation.peak_at is None:
                timing = "peak_unknown"
            elif posted_at < observation.peak_at:
                timing = "pre_peak"
            else:
                timing = "post_peak"
            output.append(XMarketJoin(lead, observation, timing))
    return tuple(sorted(output, key=lambda item: (
        item.observation.chain, item.lead.address,
        item.lead.published_at, item.lead.status_url,
    )))


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
