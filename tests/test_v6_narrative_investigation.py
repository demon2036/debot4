from dataclasses import replace
from datetime import timedelta

from debot4.v6.narrative import (
    CapitalContext,
    CarrierBinding,
    CarrierCandidate,
    ConsensusStage,
    CurrentSignalBoundary,
    EndorsementScope,
    NarrativeAction,
    NarrativeEventKind,
    NarrativeVerdict,
    PumpPhase,
    active_investigation_request,
    investigate_narrative,
    passive_investigation_request,
)
from tests.v6_narrative_case import (
    NOW,
    OTHER,
    REGISTRY,
    TOKEN,
    complete_case,
    event,
)


def _active(events=None, carriers=None, capital=None, trigger_event_id=None):
    case = complete_case()
    return active_investigation_request(
        trigger_id="active:expert",
        trigger_event_id=case.catalyst_id if trigger_event_id is None else trigger_event_id,
        narrative_key="example-narrative",
        as_of=NOW,
        events=case.events if events is None else events,
        carriers=case.carriers if carriers is None else carriers,
        capital=case.capital if capital is None else capital,
        pump_phase=PumpPhase.PRE_PUMP,
        invalidation_conditions=("official actor retracts the exact CA",),
    )


def _passive(events=None, carriers=None, capital=None, trigger=TOKEN):
    case = complete_case()
    return passive_investigation_request(
        trigger_id="debot:current",
        trigger_token=trigger,
        narrative_key="example-narrative",
        as_of=NOW,
        events=case.events if events is None else events,
        carriers=case.carriers if carriers is None else carriers,
        capital=case.capital if capital is None else capital,
        pump_phase=PumpPhase.PRE_PUMP,
        invalidation_conditions=("official actor retracts the exact CA",),
    )


def _run(request):
    return investigate_narrative(request, actor_registry=REGISTRY)


def test_active_and_passive_entrances_share_one_causal_conclusion() -> None:
    case = complete_case()
    active = _run(_active())
    passive = _run(_passive())

    assert active.verdict is passive.verdict is NarrativeVerdict.BUY_CANDIDATE
    assert active.stage is passive.stage is ConsensusStage.VALIDATION
    assert active.source_event_id == passive.source_event_id == case.source_id
    assert active.current_catalyst_id == passive.current_catalyst_id == case.catalyst_id
    assert active.narrative_leader == passive.narrative_leader == TOKEN
    assert active.historical_kol_confirmed and active.current_debot_confirmed


def test_capital_signals_cannot_replace_independent_story_propagation() -> None:
    case = complete_case()
    events = tuple(item for item in case.events if item.event_id not in case.propagation_ids)
    report = _run(_active(events=events))

    assert report.verdict is NarrativeVerdict.WAIT
    assert report.stage is ConsensusStage.DISCOVERY
    assert "independent_narrative_propagation_unresolved" in report.reasons


def test_historical_kol_confirmation_expires_at_the_decision_boundary() -> None:
    case = complete_case()
    current = case.capital.current_debot
    assert current is not None
    stale = CurrentSignalBoundary(
        "stale", NOW - timedelta(days=31), NOW - timedelta(days=31) + timedelta(seconds=1)
    )
    capital = CapitalContext((stale,), current, True)
    report = _run(_active(capital=capital))

    assert report.verdict is NarrativeVerdict.WAIT
    assert report.historical_kol_confirmed is False
    assert "recent_historical_kol_confirmation_missing" in report.reasons


def test_post_cutoff_active_trigger_is_not_backfilled_into_the_timeline() -> None:
    case = complete_case()
    future = event(
        "future-catalyst", NarrativeEventKind.CURRENT_CATALYST, "expert", 1,
        parents=(case.source_id,),
    )
    visible = tuple(
        item for item in case.events
        if item.event_id in {case.source_id, case.binding_id}
    )
    request = _active(
        events=visible + (future,), trigger_event_id=future.event_id,
    )
    report = _run(request)

    assert report.verdict is NarrativeVerdict.WAIT
    assert report.current_catalyst_id is None
    assert future.event_id not in report.timeline


def test_passive_copycat_trigger_is_rejected_even_if_debot_saw_it() -> None:
    case = complete_case()
    copycat = CarrierCandidate(
        OTHER, "FAKE", "Copycat", CarrierBinding.UNVERIFIED, (),
        NOW - timedelta(minutes=70), NOW - timedelta(minutes=69),
        100_000, NOW - timedelta(seconds=1),
    )
    report = _run(_passive(carriers=case.carriers + (copycat,), trigger=OTHER))

    assert report.verdict is NarrativeVerdict.REJECT
    assert "debot_trigger_is_not_narrative_leader" in report.reasons


def test_authoritative_denial_rejects_the_bound_carrier() -> None:
    case = complete_case()
    denial = event(
        "denial", NarrativeEventKind.COUNTER_EVIDENCE, "official", -2,
        parents=(case.source_id,), token=TOKEN,
    )
    report = _run(_active(events=case.events + (denial,)))

    assert report.verdict is NarrativeVerdict.REJECT
    assert report.counterevidence_ids == (denial.event_id,)
    assert "authoritative_counterevidence" in report.reasons


def test_propagation_kol_cannot_self_assign_exact_ca_authority() -> None:
    case = complete_case()
    kol_report = event(
        "kol-ca-report", NarrativeEventKind.PROPAGATION, "kol", -90,
        parents=(case.source_id,), token=TOKEN,
    )
    assert kol_report.exact_ca is False
    assert kol_report.token_address == ""
    events = tuple(item for item in case.events if item.event_id != case.binding_id) + (
        kol_report,
    )
    carrier = replace(case.carriers[0], binding_event_ids=(kol_report.event_id,))
    report = _run(_active(events=events, carriers=(carrier,)))

    assert report.verdict is NarrativeVerdict.WAIT
    assert report.carrier_binding is CarrierBinding.UNVERIFIED
    assert "narrative_leader_unresolved" in report.reasons
