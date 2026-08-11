"""Immutable v6 research inputs and source observations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import re

from .domain import TokenRef
from .fxtwitter import FxTwitterTweet

RESEARCH_SCHEMA = "v6.live_narrative_research.v1"
DEBOT_KOL_SOURCE = "debot:bsc:official-signal"
DEBOT_RANKS_SOURCE = "debot:bsc:ranks"
KOL_BUY_EVIDENCE_SCHEMA = "debot.v6.kol_buy_evidence.v1"
KOL_PROXY_EVIDENCE_SCHEMA = "debot.v6.kol_participation_proxy.v1"
KOL_QUALIFICATION_REASON = "provider_ui_buy_with_windowed_wallet_trades"
_BSC_ADDRESS = re.compile(r"0x[0-9a-fA-F]{40}")


class ResearchOutcome(str, Enum):
    FETCHED = "fetched"
    WAIT = "wait"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class CurrentSignalBoundary:
    signal_id: str
    event_at: datetime
    available_at: datetime

    def __post_init__(self) -> None:
        signal_id = self.signal_id.strip()
        event_at = aware_utc(self.event_at, "event_at")
        available_at = aware_utc(self.available_at, "available_at")
        if not signal_id:
            raise ValueError("signal_id is required")
        if event_at > available_at:
            raise ValueError("event_at cannot be after available_at")
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "event_at", event_at)
        object.__setattr__(self, "available_at", available_at)

    def to_payload(self) -> dict[str, str]:
        return {
            "signal_id": self.signal_id,
            "event_at": self.event_at.isoformat(),
            "available_at": self.available_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class HistoricalKolFact:
    evidence_identity: str
    token_address: str
    signal_id: str
    event_time: datetime
    available_at: datetime
    qualified_at: datetime
    inserted_at: datetime
    source: str
    metadata_json: str

    def __post_init__(self) -> None:
        identity = self.evidence_identity.strip()
        signal_id = self.signal_id.strip()
        token = self.token_address.strip().lower()
        if not identity or not signal_id:
            raise ValueError("evidence_identity and signal_id are required")
        if not _BSC_ADDRESS.fullmatch(token):
            raise ValueError("token_address must be an exact BSC address")
        if not isinstance(self.metadata_json, str):
            raise ValueError("metadata_json must be a string")
        object.__setattr__(self, "evidence_identity", identity)
        object.__setattr__(self, "signal_id", signal_id)
        object.__setattr__(self, "token_address", token)
        for field in ("event_time", "available_at", "qualified_at", "inserted_at"):
            object.__setattr__(self, field, aware_utc(getattr(self, field), field))

    @classmethod
    def from_record(cls, record: object) -> "HistoricalKolFact":
        return cls(
            evidence_identity=str(getattr(record, "evidence_identity")),
            token_address=str(getattr(record, "token_address")),
            signal_id=str(getattr(record, "signal_id")),
            event_time=getattr(record, "event_time"),
            available_at=getattr(record, "available_at"),
            qualified_at=getattr(record, "qualified_at"),
            inserted_at=getattr(record, "inserted_at"),
            source=str(getattr(record, "source")),
            metadata_json=str(getattr(record, "metadata_json")),
        )


@dataclass(frozen=True, slots=True)
class StatusResearch:
    token: TokenRef
    outcome: ResearchOutcome
    reason: str
    lead_identity: str
    lead_url: str | None
    requested_handle: str | None
    requested_status_id: str | None
    lead_available_at: datetime
    tweet: FxTwitterTweet | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "outcome", ResearchOutcome(self.outcome))
        object.__setattr__(
            self, "lead_available_at",
            aware_utc(self.lead_available_at, "lead_available_at"),
        )
        if not self.reason.strip() or not self.lead_identity.strip():
            raise ValueError("research reason and lead identity are required")
        if self.outcome is ResearchOutcome.FETCHED and self.tweet is None:
            raise ValueError("fetched research requires a tweet")

    def to_payload(self) -> dict[str, object]:
        tweet = self.tweet
        return {
            "outcome": self.outcome.value,
            "reason": self.reason,
            "token": {"chain": self.token.chain, "address": self.token.address},
            "lead_identity": self.lead_identity,
            "lead_url": self.lead_url,
            "requested_handle": self.requested_handle,
            "requested_status_id": self.requested_status_id,
            "lead_available_at": self.lead_available_at.isoformat(),
            "tweet": None if tweet is None else {
                "tweet_id": tweet.tweet_id,
                "author_handle": tweet.author_handle,
                "author_id": tweet.author_id,
                "published_at": tweet.published_at.isoformat(),
                "fetched_at": tweet.fetched_at.isoformat(),
                "canonical_url": tweet.canonical_url,
                "text_sha256": sha256(tweet.text.encode("utf-8")).hexdigest(),
            },
        }


def aware_utc(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def is_exact_bsc_token(token: TokenRef) -> bool:
    return token.chain == "bsc" and bool(_BSC_ADDRESS.fullmatch(token.address))
