from debot4.v6.golden_dogs.narrative_source_audit import (
    build_narrative_source_audit, narrative_target_counts,
)
import pytest


def _event(occurred_at, semantic, url="https://x.com/a/status/1"):
    return {
        "occurred_at": occurred_at,
        "actor": "a",
        "semantic": semantic,
        "url": url,
        "payload_sha256": "a" * 64,
    }


def test_separates_upstream_source_and_meaningful_exact_ca_publication():
    result = build_narrative_source_audit(
        upstream_sources=({
            "status": "verified",
            "published_at": "2026-08-06T00:00:00Z",
            "status_url": "https://x.com/source/status/1",
            "payload_sha256": "b" * 64,
        },),
        x_evidence_by_phase={
            "pre_trough": (
                _event("2026-08-06T00:01:00Z", "scanner"),
                _event(
                    "2026-08-06T00:02:00Z", "market_thesis",
                    "https://x.com/a/status/2",
                ),
            ),
        },
        manual_conclusion="reviewed",
        token_created_at=1785974580,
    )

    assert result["upstream_source_status"] == "verified"
    assert result["origin_resolution"] == "verified_upstream_source"
    assert result["earliest_exact_ca_observation"]["semantic"] == "scanner"
    meaningful = result["earliest_meaningful_exact_ca_publication"]
    assert meaningful["semantic"] == "market_thesis"
    assert meaningful["relation_to_token_creation"] == "before_creation"
    assert result["meaningful_exact_ca_before_creation"] is True


def test_scanner_only_does_not_become_a_narrative_source():
    result = build_narrative_source_audit(
        upstream_sources=({
            "status": "unavailable",
            "published_at": None,
            "status_url": "https://x.com/deleted/status/1",
            "payload_sha256": None,
        },),
        x_evidence_by_phase={
            "ascent": (_event("2026-08-06T00:02:00Z", "scanner"),),
        },
        manual_conclusion="original source unresolved",
        token_created_at=1785974460,
    )

    assert result["upstream_source_status"] == "candidate_unavailable"
    assert result["origin_resolution"] == "upstream_candidate_unavailable"
    assert result["earliest_meaningful_exact_ca_publication"] is None
    assert result["meaningful_exact_ca_before_creation"] is False


def test_target_counts_deduplicate_waves_and_reject_inconsistent_audits():
    audit = {
        "upstream_source_status": "verified",
        "earliest_meaningful_exact_ca_publication": {"url": "x"},
        "meaningful_exact_ca_before_creation": True,
    }
    rows = ({"label": "A", "narrative_source_audit": audit},
            {"label": "A", "narrative_source_audit": audit})
    assert narrative_target_counts(rows) == {
        "verified_upstream_source": 1,
        "unavailable_upstream_candidate": 0,
        "meaningful_exact_ca_publication": 1,
        "meaningful_exact_ca_before_creation": 1,
    }
    changed = {
        **audit,
        "earliest_meaningful_exact_ca_publication": {"url": "different"},
    }
    with pytest.raises(ValueError, match="changed across waves"):
        narrative_target_counts((*rows, {
            "label": "A", "narrative_source_audit": changed,
        }))
