"""Strictly parse Grok's untrusted, score-free narrative brief."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
import re


class GrokBriefError(ValueError):
    """The search answer did not contain a valid bounded narrative brief."""

class EventRole(str, Enum):
    SOURCE = "source"
    CATALYST = "catalyst"
    AMPLIFICATION = "amplification"
    COUNTER = "counter"
    UNKNOWN = "unknown"

class NarrativePhase(str, Enum):
    LATENT = "latent"
    DISCOVERY = "discovery"
    VALIDATION = "validation"
    EXPANSION = "expansion"
    SATURATION = "saturation"
    DECAY = "decay"
    REVIVAL = "revival"
    UNKNOWN = "unknown"

class CatalystType(str, Enum):
    SOURCE_EVENT = "source_event"
    OFFICIAL_ADOPTION = "official_adoption"
    CREATOR_ACTION = "creator_action"
    ECOSYSTEM_ACTOR_ACTION = "ecosystem_actor_action"
    KOL_AMPLIFICATION = "kol_amplification"
    COMMUNITY_REMIX = "community_remix"
    MARKET_ANOMALY = "market_anomaly"
    OLD_NARRATIVE_REVIVAL = "old_narrative_revival"
    NO_PUBLIC_CATALYST = "no_public_catalyst"
    UNKNOWN = "unknown"

class CaCarrierStatus(str, Enum):
    NO_CA = "no_ca"
    SINGLE_CANDIDATE = "single_candidate"
    OPEN_RACE = "open_race"
    LEADERS_ALIGNED = "leaders_aligned"
    LEADERS_SPLIT = "leaders_split"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"

_CHAIN = re.compile(r"[a-z0-9][a-z0-9_-]{1,31}")
_EVM_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")
_EVM_CHAINS = {
    "arbitrum", "avalanche", "base", "berachain", "bsc", "ethereum",
    "fantom", "linea", "mantle", "opbnb", "optimism", "polygon",
    "pulsechain", "scroll", "sonic", "unichain", "zksync",
}
_FORBIDDEN_KEYS = {
    "buy", "buy_signal", "decision", "entry_price", "score", "should_buy",
    "target_price", "trade_action",
}


@dataclass(frozen=True, slots=True)
class CaReference:
    """An exact contract candidate; it is not an endorsement."""

    chain: str
    address: str
    symbol: str = ""

    def __post_init__(self) -> None:
        chain = _text(self.chain, "carrier chain", 2, 32).lower()
        address = _text(self.address, "carrier address", 4, 128)
        symbol = _text(self.symbol, "carrier symbol", 0, 32)
        if not _CHAIN.fullmatch(chain) or any(char.isspace() for char in address):
            raise GrokBriefError("CA reference identity is invalid")
        if chain in _EVM_CHAINS and not _EVM_ADDRESS.fullmatch(address):
            raise GrokBriefError("EVM CA must be an exact 20-byte address")
        object.__setattr__(self, "chain", chain)
        object.__setattr__(self, "address", address.lower() if address.startswith("0x") else address)
        object.__setattr__(self, "symbol", symbol)

    @property
    def identity(self) -> tuple[str, str]:
        return self.chain, self.address


@dataclass(frozen=True, slots=True)
class GrokNarrativeBrief:
    """A search hypothesis. None of its fields are evidence or trade authority."""

    narrative_key: str
    one_line_meme: str
    event_role: EventRole
    why_now: str
    unknowns: tuple[str, ...]
    narrative_source_summary: str = ""
    propagation_engine: tuple[str, ...] = ()
    future_24h_path: tuple[str, ...] = ()
    ca_carrier_status: CaCarrierStatus = CaCarrierStatus.UNKNOWN
    competing_cas: tuple[CaReference, ...] = ()
    narrative_leader: CaReference | None = None
    market_leader: CaReference | None = None
    phase: NarrativePhase = NarrativePhase.UNKNOWN
    catalyst_type: CatalystType = CatalystType.UNKNOWN
    counter_evidence: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "narrative_key", _text(self.narrative_key, "narrative_key", 2, 120))
        object.__setattr__(self, "one_line_meme", _text(self.one_line_meme, "one_line_meme", 2, 500))
        object.__setattr__(self, "why_now", _text(self.why_now, "why_now", 0, 1_000))
        object.__setattr__(self, "narrative_source_summary", _text(
            self.narrative_source_summary, "narrative_source_summary", 0, 2_000
        ))
        object.__setattr__(self, "unknowns", _items(self.unknowns, "unknowns", 32, 1_000))
        object.__setattr__(self, "propagation_engine", _items(
            self.propagation_engine, "propagation_engine", 12, 1_000
        ))
        object.__setattr__(self, "future_24h_path", _items(
            self.future_24h_path, "future_24h_path", 12, 1_000
        ))
        object.__setattr__(self, "counter_evidence", _items(
            self.counter_evidence, "counter_evidence", 32, 1_000
        ))
        object.__setattr__(self, "invalidation_conditions", _items(
            self.invalidation_conditions, "invalidation_conditions", 32, 1_000
        ))
        try:
            object.__setattr__(self, "event_role", EventRole(self.event_role))
            object.__setattr__(self, "phase", NarrativePhase(self.phase))
            object.__setattr__(self, "catalyst_type", CatalystType(self.catalyst_type))
            status = CaCarrierStatus(self.ca_carrier_status)
        except ValueError as exc:
            raise GrokBriefError("narrative brief enum is invalid") from exc
        carriers = _carriers(self.competing_cas)
        leader = _carrier_value(self.narrative_leader, "narrative_leader")
        market = _carrier_value(self.market_leader, "market_leader")
        _validate_carrier_state(status, carriers, leader, market)
        object.__setattr__(self, "ca_carrier_status", status)
        object.__setattr__(self, "competing_cas", carriers)
        object.__setattr__(self, "narrative_leader", leader)
        object.__setattr__(self, "market_leader", market)

    @property
    def propagation_engines(self) -> tuple[str, ...]:
        """Plural alias for callers that treat engines as a collection."""
        return self.propagation_engine


def parse_narrative_brief(text: str) -> GrokNarrativeBrief:
    payload = brief_payload_object(text)
    try:
        _reject_trade_directives(payload)
        return GrokNarrativeBrief(
            narrative_key=_field(payload, "narrative_key", ""),
            one_line_meme=_field(payload, "one_line_meme", ""),
            event_role=EventRole(_field(payload, "event_role", "unknown")),
            why_now=_field(payload, "why_now", ""),
            unknowns=_list_field(payload, "unknowns"),
            narrative_source_summary=_field(payload, "narrative_source_summary", ""),
            propagation_engine=_list_field(payload, "propagation_engine"),
            future_24h_path=_list_field(payload, "future_24h_path"),
            ca_carrier_status=CaCarrierStatus(_field(payload, "ca_carrier_status", "unknown")),
            competing_cas=_carrier_list(payload.get("competing_cas", [])),
            narrative_leader=_carrier_payload(payload.get("narrative_leader"), "narrative_leader"),
            market_leader=_carrier_payload(payload.get("market_leader"), "market_leader"),
            phase=NarrativePhase(_field(payload, "phase", "unknown")),
            catalyst_type=CatalystType(_field(payload, "catalyst_type", "unknown")),
            counter_evidence=_list_field(payload, "counter_evidence"),
            invalidation_conditions=_list_field(payload, "invalidation_conditions"),
        )
    except (TypeError, ValueError):
        raise GrokBriefError("Grok narrative JSON schema is invalid") from None


def _text(value: object, name: str, minimum: int, maximum: int) -> str:
    if not isinstance(value, str):
        raise GrokBriefError(f"{name} must be text")
    cleaned = value.strip()
    if not minimum <= len(cleaned) <= maximum:
        raise GrokBriefError(f"{name} exceeds bounds")
    return cleaned


def _items(value: object, name: str, maximum: int, item_maximum: int) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise GrokBriefError(f"{name} must be an array")
    if len(value) > maximum:
        raise GrokBriefError(f"{name} exceeds bounds")
    cleaned = (_text(item, name, 1, item_maximum) for item in value)
    return tuple(dict.fromkeys(cleaned))


def _field(payload: dict[str, object], name: str, default: str) -> str:
    value = payload.get(name, default)
    if not isinstance(value, str):
        raise GrokBriefError(f"{name} must be text")
    return value


def _list_field(payload: dict[str, object], name: str) -> tuple[str, ...]:
    value = payload.get(name, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise GrokBriefError(f"{name} must be a text array")
    return tuple(value)


def _carrier_payload(value: object, name: str) -> CaReference | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise GrokBriefError(f"{name} must be an object or null")
    return CaReference(
        _field(value, "chain", ""),
        _field(value, "address", ""),
        _field(value, "symbol", ""),
    )


def _carrier_list(value: object) -> tuple[CaReference, ...]:
    if not isinstance(value, list) or len(value) > 32:
        raise GrokBriefError("competing_cas must be a bounded array")
    return tuple(_carrier_payload(item, "competing_cas") for item in value)  # type: ignore[arg-type]


def _carrier_value(value: object, name: str) -> CaReference | None:
    if value is None or isinstance(value, CaReference):
        return value
    raise GrokBriefError(f"{name} must be a CA reference")


def _carriers(value: object) -> tuple[CaReference, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > 32:
        raise GrokBriefError("competing_cas must be a bounded array")
    unique: dict[tuple[str, str], CaReference] = {}
    for item in value:
        carrier = _carrier_value(item, "competing_cas")
        if carrier is None:
            raise GrokBriefError("competing_cas cannot contain null")
        prior = unique.get(carrier.identity)
        if prior is not None and prior != carrier:
            raise GrokBriefError("duplicate CA references conflict")
        unique[carrier.identity] = carrier
    return tuple(unique.values())


def _validate_carrier_state(
    status: CaCarrierStatus,
    carriers: tuple[CaReference, ...],
    narrative: CaReference | None,
    market: CaReference | None,
) -> None:
    if status is CaCarrierStatus.NO_CA and (carriers or narrative or market):
        raise GrokBriefError("no_ca cannot identify a carrier")
    if status is CaCarrierStatus.SINGLE_CANDIDATE and len(carriers) > 1:
        raise GrokBriefError("single_candidate cannot contain competing CAs")
    if status is CaCarrierStatus.OPEN_RACE and len(carriers) < 2:
        raise GrokBriefError("open_race requires competing CAs")
    if status is CaCarrierStatus.LEADERS_ALIGNED and (
        narrative is None or market is None or narrative.identity != market.identity
    ):
        raise GrokBriefError("leaders_aligned requires one shared leader")
    if status is CaCarrierStatus.LEADERS_SPLIT and (
        narrative is None or market is None or narrative.identity == market.identity
    ):
        raise GrokBriefError("leaders_split requires distinct leaders")


def _reject_trade_directives(value: object) -> None:
    if isinstance(value, dict):
        if any(str(key).casefold() in _FORBIDDEN_KEYS for key in value):
            raise GrokBriefError("narrative brief cannot direct a trade")
        for item in value.values():
            _reject_trade_directives(item)
    elif isinstance(value, list):
        for item in value:
            _reject_trade_directives(item)


def brief_payload_object(text: str) -> dict[str, object]:
    if not isinstance(text, str) or len(text) > 200_000:
        raise GrokBriefError("Grok narrative answer is invalid")
    decoder = json.JSONDecoder()
    candidate: dict[str, object] | None = None
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "narrative_key" in value:
            candidate = value
    if candidate is None:
        raise GrokBriefError("Grok narrative answer has no JSON brief")
    return candidate
