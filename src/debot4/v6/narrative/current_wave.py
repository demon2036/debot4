"""Decision-time validation of a fresh official DeBot signal wave."""

from __future__ import annotations

from datetime import datetime

from .domain import TokenRef
from .gate_models import CurrentWaveAssessment, CurrentWaveInput, GateStatus
from .models import aware_utc, is_exact_bsc_token


_QUALITY = {
    "kol": "provider_ui_asserted",
    "smartmoney": "provider_aggregate_asserted",
}


def assess_current_wave(
    wave: CurrentWaveInput | None,
    *,
    token: TokenRef,
    decided_at: datetime,
    maximum_age_seconds: float,
) -> CurrentWaveAssessment:
    cutoff = aware_utc(decided_at, "decided_at")
    if wave is None:
        return CurrentWaveAssessment(
            GateStatus.WAIT,
            ("current_debot_wave_missing",),
            maximum_age_seconds=maximum_age_seconds,
        )
    group = (
        wave.group.split("#", 1)[0]
        .replace("_", "")
        .replace(" ", "")
        .casefold()
    )
    rejects: list[str] = []
    waits: list[str] = []
    if not is_exact_bsc_token(token) or wave.token_address != token.address:
        rejects.append("current_wave_token_mismatch")
    if group not in _QUALITY:
        rejects.append("current_wave_group_unsupported")
    if not wave.signal_identity:
        rejects.append("current_wave_identity_missing")
    if not all(
        isinstance(value, bool)
        for value in (wave.qualified, wave.security_passed, wave.chain_verified)
    ):
        rejects.append("current_wave_boolean_contract_invalid")
    if not wave.provider_at <= wave.available_at <= wave.assessed_at <= cutoff:
        rejects.append("current_wave_time_order_invalid")
    if wave.chain_verified is not False:
        rejects.append("provider_wave_false_chain_verification_claim")
    expected = _QUALITY.get(group)
    if expected is not None and wave.evidence_quality != expected:
        rejects.append("current_wave_evidence_quality_invalid")
    if wave.security_passed is False:
        rejects.extend(wave.reasons or ("current_wave_security_rejected",))
    if wave.qualified is False:
        waits.extend(wave.reasons or ("current_wave_not_qualified",))
    provider_age = (cutoff - wave.provider_at).total_seconds()
    available_age = (cutoff - wave.available_at).total_seconds()
    assessed_age = (cutoff - wave.assessed_at).total_seconds()
    age = max(provider_age, available_age, assessed_age)
    if not rejects and age > maximum_age_seconds:
        waits.append("current_debot_wave_stale")
    status = GateStatus.REJECT if rejects else GateStatus.WAIT if waits else GateStatus.PASS
    reasons = tuple(dict.fromkeys(rejects or waits or ["current_debot_wave_fresh"]))
    return CurrentWaveAssessment(
        status=status,
        reasons=reasons,
        group=wave.group,
        signal_identity=wave.signal_identity,
        provider_at=wave.provider_at,
        available_at=wave.available_at,
        assessed_at=wave.assessed_at,
        age_seconds=age,
        maximum_age_seconds=maximum_age_seconds,
        evidence_quality=wave.evidence_quality,
        chain_verified=wave.chain_verified,
    )
