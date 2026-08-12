from debot4.v6.golden_dogs.audit_summary import AuditOutcome, assess_audit_row


def row(*, clean=True, complete=True, **screen):
    manipulation = {
        "genuine_kol_swap": True, "shared_funding": False,
        "concentrated_supply": False, "wash_or_circular_trading": False,
    }
    manipulation.update(screen)
    return {
        "address": "0x" + "a" * 40,
        "gmgn_history_coverage_complete": complete,
        "verified_kol_buys": [{"clean_in_window": clean, "causal_pre_peak": clean}],
        "manipulation": manipulation,
    }


def test_complete_clean_three_gate_row_passes() -> None:
    result = assess_audit_row(row())
    assert result.outcome is AuditOutcome.PASS
    assert result.causal_pre_peak_buy is True


def test_missing_wash_check_stays_wait() -> None:
    result = assess_audit_row(row(wash_or_circular_trading=None))
    assert result.outcome is AuditOutcome.WAIT
    assert result.reasons == ("manipulation_checks_incomplete",)


def test_shared_funding_rejects_even_with_real_swap() -> None:
    result = assess_audit_row(row(shared_funding=True))
    assert result.outcome is AuditOutcome.REJECT
    assert result.reasons == ("shared_funding_detected",)


def test_no_clean_buy_rejects_only_after_complete_history() -> None:
    assert assess_audit_row(row(clean=False)).outcome is AuditOutcome.REJECT
    assert assess_audit_row(row(clean=False, complete=False)).outcome is AuditOutcome.WAIT
