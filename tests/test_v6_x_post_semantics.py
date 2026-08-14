from debot4.v6.golden_dogs.x_post_semantics import (
    XPostInterpretation,
    XPostSemantic,
    assess_x_post_semantic,
)


def interpretation(**changes) -> XPostInterpretation:
    values = {
        "semantic": XPostSemantic.MARKET_THESIS,
        "manually_reviewed": True,
        "structural_signal_candidate": True,
    }
    values.update(changes)
    return XPostInterpretation(**values)


def test_reviewed_position_or_thesis_can_be_causal_research_candidate() -> None:
    assert assess_x_post_semantic(interpretation()).causal_research_candidate
    assert assess_x_post_semantic(interpretation(
        semantic=XPostSemantic.OWN_POSITION,
    )).causal_research_candidate
    assert assess_x_post_semantic(interpretation(
        semantic=XPostSemantic.BARE_CALL,
    )).causal_research_candidate


def test_recap_and_negative_mention_are_not_forward_signals() -> None:
    for semantic in (
        XPostSemantic.RECAP,
        XPostSemantic.NEGATIVE_WARNING,
        XPostSemantic.SCANNER,
        XPostSemantic.PHISHING_LURE,
    ):
        result = assess_x_post_semantic(interpretation(semantic=semantic))
        assert result.causal_research_candidate is False


def test_unreviewed_post_cannot_be_promoted_by_timing_or_wallet() -> None:
    result = assess_x_post_semantic(interpretation(manually_reviewed=False))
    assert result.reasons == ("post_semantic_unreviewed",)


def test_semantics_do_not_replace_structural_kol_buy_evidence() -> None:
    result = assess_x_post_semantic(interpretation(
        structural_signal_candidate=False,
    ))
    assert result.causal_research_candidate is False


def test_excluded_account_role_wins_over_post_semantics() -> None:
    result = assess_x_post_semantic(interpretation(excluded_account_role=True))
    assert result.reasons == ("excluded_account_role",)
