"""Read-only codec for durable mint-alert gate state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Any, Mapping

from ..identity import utc_datetime
from .catalyst_mint import CatalystMintMatch
from .catalyst_mint_payload import catalyst_mint_from_payload, catalyst_mint_payload
from .mint_alert_policy import MintAlertAction


GATE_SCHEMA = "debot4.v6.mint-alert-gate.v1"


class MintAlertGateStateError(ValueError):
    """Durable mint-alert gate state is malformed or contradictory."""


@dataclass(frozen=True, slots=True)
class MintAlertGateGroup:
    tweet_id: str
    matches: tuple[CatalystMintMatch, ...]
    outcome: str
    reason: str
    selected_match_id: str | None
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class MintAlertGateState:
    policy_started_at: datetime
    groups: tuple[MintAlertGateGroup, ...]


def read_mint_alert_gate_state(
    path: str | Path, *, max_groups: int = 2_048,
) -> MintAlertGateState | None:
    target = Path(path)
    if not target.exists():
        return None
    if target.is_symlink() or not target.is_file():
        raise MintAlertGateStateError("mint alert gate must be a regular file")
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
        return decode_mint_alert_gate_state(raw, max_groups=max_groups)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise MintAlertGateStateError("cannot read mint alert gate") from exc


def decode_mint_alert_gate_state(
    raw: Mapping[str, Any], *, max_groups: int = 2_048,
) -> MintAlertGateState:
    if not isinstance(raw, dict) or set(raw) != {
        "schema", "policy_started_at", "groups",
    }:
        raise ValueError("invalid mint alert gate structure")
    groups_raw = raw["groups"]
    if raw["schema"] != GATE_SCHEMA or not isinstance(groups_raw, list):
        raise ValueError("unsupported mint alert gate schema")
    if len(groups_raw) > max_groups:
        raise ValueError("mint alert gate exceeds configured bounds")
    groups = tuple(_decode_group(item) for item in groups_raw)
    if len({item.tweet_id for item in groups}) != len(groups):
        raise ValueError("duplicate tweet group in mint alert gate")
    return MintAlertGateState(
        utc_datetime(datetime.fromisoformat(str(raw["policy_started_at"]))),
        groups,
    )


def encode_mint_alert_gate_state(state: MintAlertGateState) -> str:
    return json.dumps({
        "schema": GATE_SCHEMA,
        "policy_started_at": state.policy_started_at.isoformat(),
        "groups": [_encode_group(item) for item in state.groups],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _decode_group(raw: Mapping[str, Any]) -> MintAlertGateGroup:
    if not isinstance(raw, dict) or set(raw) != {
        "tweet_id", "matches", "outcome", "reason",
        "selected_match_id", "updated_at",
    }:
        raise ValueError("invalid mint alert gate group structure")
    matches_raw = raw["matches"]
    if not isinstance(matches_raw, list):
        raise ValueError("mint alert gate matches must be a list")
    matches = tuple(catalyst_mint_from_payload(item) for item in matches_raw)
    tweet_id = str(raw["tweet_id"])
    match_ids = {item.match_id for item in matches}
    if (
        not matches
        or len(match_ids) != len(matches)
        or any(item.catalyst_tweet_id != tweet_id for item in matches)
    ):
        raise ValueError("invalid mint alert gate group")
    raw_outcome = str(raw["outcome"])
    outcome = (
        "pending"
        if raw_outcome == "pending"
        else MintAlertAction(raw_outcome).value
    )
    selected = raw["selected_match_id"]
    if selected is not None:
        selected = str(selected)
        if selected not in match_ids:
            raise ValueError("mint alert selected match is absent")
    if outcome == MintAlertAction.ALERT.value and selected is None:
        raise ValueError("alerting mint group has no selected match")
    return MintAlertGateGroup(
        tweet_id=tweet_id,
        matches=matches,
        outcome=outcome,
        reason=str(raw["reason"]),
        selected_match_id=selected,
        updated_at=utc_datetime(datetime.fromisoformat(str(raw["updated_at"]))),
    )


def _encode_group(group: MintAlertGateGroup) -> dict[str, object]:
    return {
        "tweet_id": group.tweet_id,
        "matches": [catalyst_mint_payload(item) for item in group.matches],
        "outcome": group.outcome,
        "reason": group.reason,
        "selected_match_id": group.selected_match_id,
        "updated_at": group.updated_at.isoformat(),
    }


__all__ = [
    "GATE_SCHEMA",
    "MintAlertGateGroup",
    "MintAlertGateState",
    "MintAlertGateStateError",
    "decode_mint_alert_gate_state",
    "encode_mint_alert_gate_state",
    "read_mint_alert_gate_state",
]
