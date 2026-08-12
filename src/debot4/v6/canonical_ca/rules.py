"""Conservative competing-CA resolver; ties and weak evidence stay unresolved."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from ..explosion import ExplosionCategory, ExplosionEvent


_EVM_CA = re.compile(r"0x[a-f0-9]{40}")


@dataclass(frozen=True, slots=True)
class CaCandidate:
    address: str
    official_post: bool = False
    official_website: bool = False
    creator_wallet: bool = False
    authority_wallet: bool = False
    holder_migration: bool = False

    def __post_init__(self) -> None:
        address = self.address.strip().casefold()
        if not _EVM_CA.fullmatch(address):
            raise ValueError("canonical candidate address is invalid")
        object.__setattr__(self, "address", address)

    @property
    def score(self) -> int:
        return (
            5 * self.official_post
            + 5 * self.official_website
            + 3 * self.creator_wallet
            + 2 * self.authority_wallet
            + self.holder_migration
        )

    @property
    def officially_bound(self) -> bool:
        return self.official_post or self.official_website


@dataclass(frozen=True, slots=True)
class CanonicalDecision:
    status: str
    leader: str
    scores: tuple[tuple[str, int], ...]


def resolve_canonical_ca(candidates: tuple[CaCandidate, ...]) -> CanonicalDecision:
    unique = {item.address: item for item in candidates}
    if len(unique) != len(candidates) or not candidates:
        raise ValueError("canonical candidates must be non-empty and unique")
    ranked = sorted(candidates, key=lambda item: (-item.score, item.address))
    winner = ranked[0]
    tied = len(ranked) > 1 and ranked[1].score == winner.score
    resolved = winner.officially_bound and not tied
    return CanonicalDecision(
        "resolved" if resolved else "unresolved",
        winner.address if resolved else "",
        tuple((item.address, item.score) for item in ranked),
    )


def leader_change_event(
    previous: CanonicalDecision,
    current: CanonicalDecision,
    *,
    subject: str,
    actor_id: str,
    actor_role: str,
    occurred_at: datetime,
    first_seen_at: datetime,
    source_url: str,
    evidence_hash: str,
    chain: str,
) -> ExplosionEvent | None:
    if current.status != "resolved" or current.leader == previous.leader:
        return None
    return ExplosionEvent(
        category=ExplosionCategory.CANONICAL_CA,
        subtype="canonical_ca_selected" if not previous.leader else "canonical_ca_changed",
        occurred_at=occurred_at,
        first_seen_at=first_seen_at,
        subject=subject,
        actor_id=actor_id,
        actor_role=actor_role,
        source_url=source_url,
        evidence_hash=evidence_hash,
        previous={"status": previous.status, "leader": previous.leader},
        current={"status": current.status, "leader": current.leader},
        confidence="verified",
        chain=chain,
        token_address=current.leader,
    )
