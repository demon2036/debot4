"""Repeatable, concurrent stable-identity audit for monitored X actors."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Protocol

from ..x import XProfile
from .actor_registry import ActorRegistry, DEFAULT_ACTOR_REGISTRY


class ProfileFetcher(Protocol):
    def fetch(self, handle: str) -> XProfile: ...


@dataclass(frozen=True, slots=True)
class ActorAuditFinding:
    handle: str
    expected_id: str
    observed_id: str = ""
    display_name: str = ""
    description: str = ""
    status: str = "unavailable"
    error_type: str = ""

    @property
    def verified(self) -> bool:
        return self.status == "verified"


@dataclass(frozen=True, slots=True)
class ActorAuditReport:
    findings: tuple[ActorAuditFinding, ...]

    @property
    def verified_count(self) -> int:
        return sum(item.verified for item in self.findings)

    @property
    def failures(self) -> tuple[ActorAuditFinding, ...]:
        return tuple(item for item in self.findings if not item.verified)


def audit_actor_registry(
    fetcher: ProfileFetcher,
    registry: ActorRegistry = DEFAULT_ACTOR_REGISTRY,
    *,
    max_workers: int = 16,
) -> ActorAuditReport:
    if isinstance(max_workers, bool) or not 1 <= max_workers <= 64:
        raise ValueError("actor audit workers must be between 1 and 64")
    registrations = registry.registrations()
    findings: dict[str, ActorAuditFinding] = {}
    with ThreadPoolExecutor(max_workers=min(max_workers, len(registrations))) as pool:
        futures = {
            pool.submit(fetcher.fetch, item.actor.handle): item
            for item in registrations
        }
        for future in as_completed(futures):
            registration = futures[future]
            actor = registration.actor
            expected_id = registration.author_ids[0]
            try:
                profile = future.result()
                status = "verified" if profile.user_id == expected_id else "id_mismatch"
                finding = ActorAuditFinding(
                    actor.handle, expected_id, profile.user_id,
                    profile.display_name, profile.description, status,
                )
            except Exception as exc:
                finding = ActorAuditFinding(
                    actor.handle, expected_id, error_type=type(exc).__name__,
                )
            findings[actor.handle.casefold()] = finding
    ordered = tuple(findings[item.actor.handle.casefold()] for item in registrations)
    return ActorAuditReport(ordered)
