"""Build an auditable boundary around upstream and Exact-CA narrative sources."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime


MEANINGFUL_EXACT_CA_SEMANTICS = frozenset({
    "bare_call",
    "market_thesis",
    "own_position",
    "project_announcement",
})


def build_narrative_source_audit(
    *,
    upstream_sources: Sequence[Mapping[str, object]],
    x_evidence_by_phase: Mapping[str, Sequence[Mapping[str, object]]],
    manual_conclusion: str,
    token_created_at: int,
) -> dict[str, object]:
    """Separate verified upstream sources from the first Exact-CA observation."""

    upstream = tuple(_timed_source(item, token_created_at) for item in upstream_sources)
    events = _unique_x_events(x_evidence_by_phase, token_created_at)
    meaningful = tuple(
        item for item in events
        if item["semantic"] in MEANINGFUL_EXACT_CA_SEMANTICS
    )
    verified_upstream = tuple(
        item for item in upstream
        if item["status"] == "verified" and item["receipt_verified"]
    )
    unavailable_upstream = tuple(
        item for item in upstream if item["status"] == "unavailable"
    )
    earliest_meaningful = meaningful[0] if meaningful else None
    return {
        "manual_conclusion": manual_conclusion,
        "upstream_source_status": _upstream_status(
            verified_upstream, unavailable_upstream,
        ),
        "upstream_sources": list(upstream),
        "earliest_exact_ca_observation": events[0] if events else None,
        "earliest_meaningful_exact_ca_publication": earliest_meaningful,
        "meaningful_exact_ca_before_creation": bool(
            earliest_meaningful
            and earliest_meaningful["relation_to_token_creation"] == "before_creation"
        ),
        "origin_resolution": _origin_resolution(
            verified_upstream, unavailable_upstream, events, meaningful,
        ),
    }


def _unique_x_events(phases, token_created_at):
    by_url: dict[str, dict[str, object]] = {}
    for phase, events in phases.items():
        for event in events:
            url = str(event["url"])
            timed = _timed_event(event, phase, token_created_at)
            existing = by_url.get(url)
            if existing is None or _event_key(timed) < _event_key(existing):
                by_url[url] = timed
    return tuple(sorted(by_url.values(), key=_event_key))


def _timed_event(event, phase, token_created_at):
    occurred_at = str(event["occurred_at"])
    timestamp = _timestamp(occurred_at)
    return {
        "occurred_at": occurred_at,
        "actor": event["actor"],
        "semantic": event["semantic"],
        "phase": phase,
        "url": event["url"],
        "payload_sha256": event["payload_sha256"],
        **_creation_timing(timestamp, token_created_at),
    }


def _timed_source(source, token_created_at):
    published_at = source.get("published_at")
    timing = (
        {"seconds_from_token_creation": None,
         "relation_to_token_creation": "time_unavailable"}
        if published_at is None
        else _creation_timing(_timestamp(str(published_at)), token_created_at)
    )
    return {
        **source,
        "receipt_verified": bool(
            source.get("status") == "verified"
            and source.get("status_url")
            and source.get("payload_sha256")
        ),
        **timing,
    }


def narrative_target_counts(rows: Sequence[Mapping[str, object]]) -> dict[str, int]:
    """Count project-level source coverage without double-counting later waves."""

    projects: dict[str, Mapping[str, object]] = {}
    for row in rows:
        label = str(row["label"])
        audit = row["narrative_source_audit"]
        prior = projects.get(label)
        if prior is not None and _target_signature(prior) != _target_signature(audit):
            raise ValueError(f"narrative source coverage changed across waves: {label}")
        projects.setdefault(label, audit)
    return {
        "verified_upstream_source": _count(
            projects, "upstream_source_status", "verified",
        ),
        "unavailable_upstream_candidate": _count(
            projects, "upstream_source_status", "candidate_unavailable",
        ),
        "meaningful_exact_ca_publication": sum(
            item["earliest_meaningful_exact_ca_publication"] is not None
            for item in projects.values()
        ),
        "meaningful_exact_ca_before_creation": sum(
            bool(item["meaningful_exact_ca_before_creation"])
            for item in projects.values()
        ),
    }


def _count(projects, key, value):
    return sum(item[key] == value for item in projects.values())


def _target_signature(audit):
    source = audit["earliest_meaningful_exact_ca_publication"]
    return (
        audit["upstream_source_status"],
        None if source is None else source["url"],
        bool(audit["meaningful_exact_ca_before_creation"]),
    )


def _creation_timing(timestamp, token_created_at):
    lead = timestamp - token_created_at
    return {
        "seconds_from_token_creation": lead,
        "relation_to_token_creation": (
            "before_creation" if lead < 0 else "at_or_after_creation"
        ),
    }


def _timestamp(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def _event_key(event):
    return _timestamp(str(event["occurred_at"])), str(event["url"])


def _upstream_status(verified, unavailable):
    if verified:
        return "verified"
    if unavailable:
        return "candidate_unavailable"
    return "not_identified"


def _origin_resolution(verified, unavailable, events, meaningful):
    if verified:
        return "verified_upstream_source"
    if meaningful:
        return "exact_ca_publication_verified_upstream_origin_unresolved"
    if unavailable:
        return "upstream_candidate_unavailable"
    if events:
        return "only_non_narrative_exact_ca_observation"
    return "no_direct_public_source_identified"
