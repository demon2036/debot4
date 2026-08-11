from __future__ import annotations

import json
from pathlib import Path

import pytest

from debot4.v6.narrative.causal_replay import (
    ClaimRole,
    ReplayVerdict,
    case_from_mapping,
    evaluate_causal_replay,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "v6_causal_replay_cases.json"


def _fixture() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cases() -> list[dict[str, object]]:
    return _fixture()["cases"]


@pytest.mark.parametrize("raw", _cases(), ids=lambda raw: raw["case_id"])
def test_causal_replay_baseline(raw: dict[str, object]) -> None:
    decision = evaluate_causal_replay(case_from_mapping(raw))
    expected = raw["expected"]

    assert decision.verdict is ReplayVerdict(expected["verdict"])
    assert expected["reason"] in decision.reasons


def test_all_non_repository_cases_are_explicitly_synthetic() -> None:
    for raw in _cases():
        provenance = raw["provenance"]
        assert provenance["kind"] in {"synthetic", "repository_corpus"}
        if provenance["kind"] == "synthetic":
            assert provenance["purpose"]

    assert "not historical trades or profit claims" in _fixture()["disclaimer"]


def test_real_retrospective_fixture_matches_repository_corpus() -> None:
    raw = next(item for item in _cases() if item["case_id"].startswith("beidou-"))
    provenance = raw["provenance"]
    rows = (
        json.loads(line)
        for line in (ROOT / provenance["path"]).read_text(encoding="utf-8").splitlines()
    )
    corpus = next(row for row in rows if row["tweet_id"] == provenance["tweet_id"])

    assert corpus["stage"] == provenance["expected_stage"] == "retrospective"
    assert raw["target_address"] in corpus["full_text"]
    assert "500K" in corpus["full_text"] and "ATH 1.6M" in corpus["full_text"]
    assert corpus["utc"] == raw["evidence"][0]["published_at"]


def test_denial_is_counter_only_never_positive_evidence() -> None:
    raw = next(item for item in _cases() if item["case_id"] == "synthetic-authoritative-denial")
    decision = evaluate_causal_replay(case_from_mapping(raw))

    assert decision.counter_evidence_ids == ("denial", "kol-denial")
    assert "denial" not in decision.causal_evidence_ids
    assert "kol-denial" not in decision.causal_evidence_ids
    assert all("denial" not in item_id for item_id, _ in decision.effective_claims)


def test_kol_and_wallet_claims_are_reduced_to_propagation() -> None:
    raw = next(
        item for item in _cases()
        if item["case_id"] == "synthetic-kol-wallet-cannot-create-catalyst-or-binding"
    )
    decision = evaluate_causal_replay(case_from_mapping(raw))
    claims = dict(decision.effective_claims)

    assert claims["kol-ca"] is ClaimRole.PROPAGATION
    assert claims["wallet-catalyst"] is ClaimRole.PROPAGATION
    assert "exact_ca_binding_missing" in decision.reasons
    assert "public_catalyst_missing" in decision.reasons


def test_fixture_has_no_claimed_returns_or_profit_labels() -> None:
    forbidden = {"pnl", "profit", "return", "peak_return_pct", "close_return_pct"}
    for raw in _cases():
        assert forbidden.isdisjoint(raw)
        assert forbidden.isdisjoint(raw["expected"])
