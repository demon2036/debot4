"""Immutable alert emitted only after a tweet-to-mint binding passes the gate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from ..identity import stable_id, utc_datetime
from .catalyst_mint import CatalystMintMatch
from .mint_qualification import MINT_QUALIFIER_MODEL


MINT_ALERT_SCHEMA = "debot4.v6.catalyst-mint-alert.v2"
_ALERT_ID_SCHEMA = "debot4.v6.catalyst-mint-alert.v1"
MINT_ALERT_SLA_SECONDS = 15.0
MINT_ALERT_DECISION_REASON = "spark_qualified_unique_catalyst_mint"
LEGACY_DECISION_REASON = "legacy_unqualified_alert"


@dataclass(frozen=True, slots=True)
class MintAlert:
    """Durable delivery envelope for one accepted catalyst-to-mint match."""

    match: CatalystMintMatch
    raised_at: datetime
    decision_reason: str
    qualification_model: str | None
    qualified_at: datetime | None
    alert_id: str = field(init=False)
    authorizes_trade: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        raised_at = utc_datetime(self.raised_at)
        if raised_at < self.match.observed_at:
            raise ValueError("mint alert predates the complete match evidence")
        reason = self.decision_reason.strip()
        model = (
            None
            if self.qualification_model is None
            else self.qualification_model.strip()
        )
        qualified = (
            None
            if self.qualified_at is None
            else utc_datetime(self.qualified_at)
        )
        if model is None or qualified is None:
            if model is not None or qualified is not None:
                raise ValueError("partial mint qualification provenance")
            if reason != LEGACY_DECISION_REASON:
                raise ValueError("mint alert lacks qualification provenance")
        else:
            if model != MINT_QUALIFIER_MODEL:
                raise ValueError("mint alert uses an unexpected qualifier model")
            if reason != MINT_ALERT_DECISION_REASON:
                raise ValueError("mint alert has an invalid decision reason")
            if qualified < self.match.observed_at or qualified > raised_at:
                raise ValueError("mint alert qualification timing is invalid")
        object.__setattr__(self, "raised_at", raised_at)
        object.__setattr__(self, "decision_reason", reason)
        object.__setattr__(self, "qualification_model", model)
        object.__setattr__(self, "qualified_at", qualified)
        object.__setattr__(
            self,
            "alert_id",
            stable_id("mint-alert", _ALERT_ID_SCHEMA, self.match.match_id),
        )

    @classmethod
    def qualified(
        cls,
        match: CatalystMintMatch,
        *,
        raised_at: datetime,
        decision_reason: str,
        qualification_model: str,
        qualified_at: datetime,
    ) -> "MintAlert":
        return cls(
            match=match,
            raised_at=raised_at,
            decision_reason=decision_reason,
            qualification_model=qualification_model,
            qualified_at=qualified_at,
        )

    @property
    def exact_ca(self) -> str:
        return self.match.exact_ca

    @property
    def detection_latency_seconds(self) -> float:
        return max(
            0.0,
            (self.raised_at - self.match.catalyst_created_at).total_seconds(),
        )

    @property
    def within_sla(self) -> bool:
        return self.detection_latency_seconds <= MINT_ALERT_SLA_SECONDS

    def as_public_dict(
        self, *, delivered_at: datetime | None = None,
    ) -> dict[str, object]:
        delivered = None if delivered_at is None else utc_datetime(delivered_at)
        delivery_latency = (
            None
            if delivered is None
            else max(
                0.0,
                (delivered - self.match.catalyst_created_at).total_seconds(),
            )
        )
        return {
            "schema": MINT_ALERT_SCHEMA,
            "event": "catalyst_mint_alert",
            "alert_id": self.alert_id,
            "chain": "bsc",
            "exact_ca": self.exact_ca,
            "catalyst": {
                "tweet_id": self.match.catalyst_tweet_id,
                "author": self.match.catalyst_author,
                "text": self.match.catalyst_text,
                "status_url": self.match.catalyst_status_url,
                "created_at": self.match.catalyst_created_at.isoformat(),
                "fetched_at": self.match.catalyst_fetched_at.isoformat(),
            },
            "match": {
                "id": self.match.match_id,
                "kind": self.match.match_kind,
                "observed_at": self.match.observed_at.isoformat(),
                "mint_delay_seconds": self.match.mint_delay_seconds,
            },
            "token": {
                "stage": self.match.token_stage,
                "created_at": self.match.token_created_at.isoformat(),
                "name": self.match.token_name,
                "symbol": self.match.token_symbol,
                "launchpad": self.match.launchpad,
                "provider_fdv_usd": (
                    None
                    if self.match.provider_fdv_usd is None
                    else format(self.match.provider_fdv_usd, "f")
                ),
                "social_urls": list(self.match.token_social_urls),
                "matched_status_url": self.match.token_status_url,
            },
            "raised_at": self.raised_at.isoformat(),
            "decision_reason": self.decision_reason,
            "qualification_model": self.qualification_model,
            "qualified_at": (
                None if self.qualified_at is None else self.qualified_at.isoformat()
            ),
            "delivered_at": None if delivered is None else delivered.isoformat(),
            "detection_latency_seconds": self.detection_latency_seconds,
            "delivery_latency_seconds": delivery_latency,
            "sla_seconds": MINT_ALERT_SLA_SECONDS,
            "within_detection_sla": self.within_sla,
            "within_delivery_sla": (
                None
                if delivery_latency is None
                else delivery_latency <= MINT_ALERT_SLA_SECONDS
            ),
            "triggered_by_raw_mint": False,
            "rpc_on_critical_path": False,
            "model_on_critical_path": self.qualification_model is not None,
            "authorizes_trade": False,
        }


__all__ = [
    "LEGACY_DECISION_REASON",
    "MINT_ALERT_DECISION_REASON",
    "MINT_ALERT_SCHEMA",
    "MINT_ALERT_SLA_SECONDS",
    "MintAlert",
]
