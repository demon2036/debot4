"""Categorical vocabulary for active and passive narrative investigations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math


class DiscoveryMode(str, Enum):
    ACTIVE_ACTOR = "active_actor"
    PASSIVE_DEBOT = "passive_debot"


class NarrativeEventKind(str, Enum):
    SOURCE_EVENT = "source_event"
    TOKEN_CREATED = "token_created"
    TOKEN_BINDING = "token_binding"
    CURRENT_CATALYST = "current_catalyst"
    PROPAGATION = "propagation"
    COUNTER_EVIDENCE = "counter_evidence"


class EvidenceProvider(str, Enum):
    X_GRAPHQL = "x_graphql"
    FXTWITTER = "fxtwitter"
    TELEGRAM_PUBLIC = "telegram_public"
    GROK_CITATION = "grok_citation"
    OFFICIAL_HTTP = "official_http"
    OFFICIAL_REPOSITORY = "official_repository"


class NarrativeAction(str, Enum):
    ORIGINATE = "originate"
    ANNOUNCE = "announce"
    LAUNCH = "launch"
    EXACT_CA_CLAIM = "exact_ca_claim"
    RELEASE = "release"
    REPLY = "reply"
    REPOST = "repost"
    QUOTE = "quote"
    REPORT = "report"
    MENTION = "mention"
    DENY = "deny"


class EndorsementScope(str, Enum):
    TOKEN_EXPLICIT = "token_explicit"
    NARRATIVE_POSITIVE = "narrative_positive"
    NARRATIVE_NEUTRAL = "narrative_neutral"
    NEGATIVE = "negative"
    NONE = "none"


class CarrierBinding(str, Enum):
    OFFICIAL_EXACT_CA = "official_exact_ca"
    CREATOR_EXACT_CA = "creator_exact_ca"
    COMMUNITY_CONSENSUS = "community_consensus"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"


class PumpPhase(str, Enum):
    PRE_PUMP = "pre_pump"
    DURING_PUMP = "during_pump"
    POST_PUMP = "post_pump"
    UNKNOWN = "unknown"


class NarrativeVerdict(str, Enum):
    BUY_CANDIDATE = "BUY_CANDIDATE"
    WAIT = "WAIT"
    REJECT = "REJECT"


@dataclass(frozen=True, slots=True)
class InvestigationPolicy:
    maximum_catalyst_age_seconds: float = 6 * 60 * 60
    maximum_historical_kol_age_seconds: float = 30 * 24 * 60 * 60
    minimum_propagation_groups: int = 2
    expansion_propagation_groups: int = 4

    def __post_init__(self) -> None:
        for name in (
            "maximum_catalyst_age_seconds",
            "maximum_historical_kol_age_seconds",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be positive")
            if not math.isfinite(float(value)) or value <= 0:
                raise ValueError(f"{name} must be positive")
            object.__setattr__(self, name, float(value))
        minimum = self.minimum_propagation_groups
        expansion = self.expansion_propagation_groups
        if isinstance(minimum, bool) or minimum < 1:
            raise ValueError("minimum_propagation_groups must be positive")
        if isinstance(expansion, bool) or expansion < minimum:
            raise ValueError("expansion groups must be at least the minimum")
