"""Self-contained, score-free narrative domain types for v6."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import re


_BSC_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")


class Readiness(str, Enum):
    PASS_TO_EXECUTION = "PASS_TO_EXECUTION"
    WAIT = "WAIT"
    REJECT = "REJECT"
    UNRESOLVED = "UNRESOLVED"


class FindingState(str, Enum):
    CONFIRMED = "confirmed"
    SUPPORTED = "supported"
    SPECULATIVE = "speculative"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


class Dimension(str, Enum):
    ORIGIN = "origin"
    LEGITIMACY = "legitimacy"
    PROPAGATION = "propagation"
    CULTURAL_FIT = "cultural_fit"
    CATALYSTS = "catalysts"
    LEADER_COMPETITION = "leader_competition"
    CONSENSUS_STAGE = "consensus_stage"
    VALUATION_ANCHOR = "valuation_anchor"
    INVALIDATION = "invalidation"


class Canonicality(str, Enum):
    OFFICIAL_EXACT_CA = "official_exact_ca"
    CREATOR_CLAIMED = "creator_claimed"
    COMMUNITY_CONSENSUS = "community_consensus"
    PROVISIONAL_LEADER = "provisional_leader"
    OPEN_RACE = "open_race"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


class ConsensusStage(str, Enum):
    LATENT = "latent"
    DISCOVERY = "discovery"
    VALIDATION = "validation"
    EXPANSION = "expansion"
    SATURATION = "saturation"
    DECAY = "decay"
    REVIVAL = "revival"
    UNRESOLVED = "unresolved"


class EvidenceRole(str, Enum):
    ORIGIN = "origin"
    TOKEN_BINDING = "token_binding"
    NARRATIVE_BINDING = "narrative_binding"
    PROPAGATION = "propagation"
    CULTURAL_CONTEXT = "cultural_context"
    CATALYST = "catalyst"
    LEADER_COMPETITION = "leader_competition"
    VALUATION = "valuation"
    COUNTER_EVIDENCE = "counter_evidence"
    CAPITAL_CONFIRMATION = "capital_confirmation"


class EvidenceSource(str, Enum):
    PRIMARY_ACTOR = "primary_actor"
    OFFICIAL_SITE = "official_site"
    ONCHAIN = "onchain"
    KOL = "kol"
    COMMUNITY = "community"
    SCANNER = "scanner"
    MARKET_DATA = "market_data"
    DEBOT = "debot"


class EvidenceScope(str, Enum):
    LIVE_ELIGIBLE = "live_eligible"
    REPLAY_ELIGIBLE = "replay_eligible"
    POSTMORTEM_ONLY = "postmortem_only"


class ValuationStatus(str, Enum):
    BOUNDED = "bounded"
    UNSUPPORTED = "unsupported"
    OVEREXTENDED = "overextended"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class TokenRef:
    chain: str
    address: str

    def __post_init__(self) -> None:
        chain = self.chain.strip().lower()
        address = self.address.strip().lower()
        if chain != "bsc" or not _BSC_ADDRESS.fullmatch(address):
            raise ValueError("v6 narrative supports exact BSC token addresses only")
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "address", address)


@dataclass(frozen=True, slots=True)
class DimensionFinding:
    dimension: Dimension
    state: FindingState
    finding: str
    supports: tuple[str, ...] = ()
    contradicts: tuple[str, ...] = ()
    unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "dimension", Dimension(self.dimension))
        object.__setattr__(self, "state", FindingState(self.state))
        if not self.finding.strip():
            raise ValueError("finding must not be empty")
        if self.state in {FindingState.CONFIRMED, FindingState.SUPPORTED} and not self.supports:
            raise ValueError("confirmed or supported findings require evidence")
        if self.state is FindingState.CONTRADICTED and not self.contradicts:
            raise ValueError("contradicted findings require counter-evidence")
