"""Pure aggregation of frozen GMGN/RPC audit rows into conservative outcomes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class AuditOutcome(str, Enum):
    PASS = "PASS"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class TokenAuditResult:
    address: str
    outcome: AuditOutcome
    verified_clean_buy: bool
    causal_pre_peak_buy: bool
    reasons: tuple[str, ...]


def assess_audit_row(row: Mapping[str, object]) -> TokenAuditResult:
    """Do not turn an RPC-verified buy into a clean-token claim."""

    address = str(row.get("address") or "")
    buys = _objects(row.get("verified_kol_buys"))
    clean = any(item.get("clean_in_window") is True for item in buys)
    causal = any(item.get("causal_pre_peak") is True for item in buys)
    manipulation = row.get("manipulation")
    screen = manipulation if isinstance(manipulation, Mapping) else {}
    unsafe = tuple(name for name, value in (
        ("kol_event_is_not_genuine_swap", screen.get("genuine_kol_swap") is False),
        ("shared_funding_detected", screen.get("shared_funding") is True),
        ("concentrated_supply", screen.get("concentrated_supply") is True),
        ("wash_or_circular_trading", screen.get("wash_or_circular_trading") is True),
    ) if value)
    if unsafe:
        return TokenAuditResult(address, AuditOutcome.REJECT, clean, causal, unsafe)
    if row.get("gmgn_history_coverage_complete") is not True:
        return TokenAuditResult(
            address, AuditOutcome.WAIT, clean, causal, ("kol_history_incomplete",),
        )
    if not clean:
        return TokenAuditResult(
            address, AuditOutcome.REJECT, False, False,
            ("no_verified_clean_gmgn_kol_buy_in_window",),
        )
    checks = tuple(screen.get(key) for key in (
        "genuine_kol_swap", "shared_funding", "concentrated_supply",
        "wash_or_circular_trading",
    ))
    if any(value is None for value in checks):
        return TokenAuditResult(
            address, AuditOutcome.WAIT, True, causal,
            ("manipulation_checks_incomplete",),
        )
    return TokenAuditResult(
        address, AuditOutcome.PASS, True, causal, ("all_three_gates_pass",),
    )


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))
