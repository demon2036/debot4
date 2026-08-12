"""Finite BOT authority baseline; no scheduler, model call, or trading path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..ecosystem_authority import (
    AuthorityNode,
    AuthorityRelationshipMonitor,
    BOT_AUTHORITY_NODES,
    FollowingClient,
    JsonFollowingSnapshotStore,
)
from ..identity_change import (
    IdentityChangeMonitor,
    JsonProfileSnapshotStore,
    ProfileMediaClient,
)
from ..x import FxEgressPool, FxJsonHttp, XProfileClient
from .store import ExplosionEventStore


@dataclass(frozen=True, slots=True)
class BaselineTargetResult:
    handle: str
    user_id: str
    identity_events: int | None
    relationship_events: int | None
    error_types: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.error_types

    def as_dict(self) -> dict[str, object]:
        return {
            "handle": self.handle,
            "user_id": self.user_id,
            "identity_events": self.identity_events,
            "relationship_events": self.relationship_events,
            "ok": self.ok,
            "error_types": list(self.error_types),
        }


def sample_bot_baseline(
    *,
    state_dir: str | Path,
    egress_config: str | Path,
    location: str,
    max_attempts: int = 3,
    scope: str = "identities",
) -> dict[str, object]:
    selected_scope = scope.strip().casefold()
    if selected_scope not in {"identities", "relationships", "all"}:
        raise ValueError("baseline scope must be identities, relationships, or all")
    root = Path(state_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    root.chmod(0o700)
    pool = FxEgressPool.from_toml(
        egress_config, location=location, max_attempts=max_attempts,
    )
    http = FxJsonHttp(opener=pool)
    profiles = XProfileClient(http=http)
    results: list[BaselineTargetResult] = []
    event_count = 0
    try:
        with ExplosionEventStore(root / "explosion-events.sqlite3") as events:
            identity = _identity_monitor(root, pool, profiles, events, selected_scope)
            relationships = _relationship_monitor(
                root, profiles, http, events, selected_scope,
            )
            for node in BOT_AUTHORITY_NODES:
                results.append(_sample_target(node, identity, relationships))
            event_count = events.count()
    finally:
        egress = pool.snapshot()
        pool.close()
    return {
        "mode": "one_shot_evidence_baseline",
        "scope": selected_scope,
        "collectors_started": False,
        "grok_triggered": False,
        "trading_started": False,
        "identity_scope": (
            "full_profile_fields" if identity is not None else "not_sampled"
        ),
        "relationship_scope": (
            "complete_following_for_every_authority_node"
            if relationships is not None else "not_sampled"
        ),
        "targets": [item.as_dict() for item in results],
        "event_count": event_count,
        "egress": egress,
    }


def _sample_target(
    node: AuthorityNode,
    identity: IdentityChangeMonitor | None,
    relationships: AuthorityRelationshipMonitor | None,
) -> BaselineTargetResult:
    identity_count: int | None = None
    relationship_count: int | None = None
    errors: list[str] = []
    if identity is not None:
        identity_count = 0
        try:
            identity_count = len(identity.poll(
                node.handle,
                actor_role=node.role,
                expected_user_id=node.user_id,
            ))
        except (RuntimeError, ValueError) as exc:
            errors.append(f"identity:{type(exc).__name__}")
    if relationships is not None:
        relationship_count = 0
        try:
            relationship_count = len(relationships.poll(node))
        except (RuntimeError, ValueError) as exc:
            errors.append(f"relationship:{type(exc).__name__}")
    return BaselineTargetResult(
        node.handle,
        node.user_id,
        identity_count,
        relationship_count,
        tuple(errors),
    )


def _identity_monitor(
    root: Path,
    pool: FxEgressPool,
    profiles: XProfileClient,
    events: ExplosionEventStore,
    scope: str,
) -> IdentityChangeMonitor | None:
    if scope not in {"identities", "all"}:
        return None
    snapshots = JsonProfileSnapshotStore(root / "x-profile-snapshots.json")
    return IdentityChangeMonitor(
        profiles, snapshots, events, ProfileMediaClient(opener=pool),
    )


def _relationship_monitor(
    root: Path,
    profiles: XProfileClient,
    http: FxJsonHttp,
    events: ExplosionEventStore,
    scope: str,
) -> AuthorityRelationshipMonitor | None:
    if scope not in {"relationships", "all"}:
        return None
    snapshots = JsonFollowingSnapshotStore(root / "x-following-snapshots.json")
    return AuthorityRelationshipMonitor(
        profiles, FollowingClient(http=http), snapshots, events,
    )
