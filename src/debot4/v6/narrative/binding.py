"""Pure, conservative exact-CA self-binding assessment for one X status."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
import re

from .domain import (
    EvidenceRole,
    EvidenceScope,
    EvidenceSource,
    TokenRef,
)
from .evidence import (
    EvidenceItem,
)
from .models import ResearchOutcome, StatusResearch, aware_utc
from .results import BindingAssessment


_ADDRESS = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
_NEGATIVE = re.compile(
    r"\b(?:fake|scam|unofficial|wrong|fraud|impersonat(?:e|or)|not\s+ours)\b"
    r"|不要买|假合约|骗局|非官方|错误合约",
    re.IGNORECASE,
)
_CUE_PREFIX = re.compile(
    r"(?:official\s+)?(?:ca|contract(?:\s+address)?|token\s+address)"
    r"\s*(?:is\s*)?[:：=\-]?\s*$|(?:官方)?(?:合约地址|合约|地址)\s*(?:是|为)?[:：=]?\s*$",
    re.IGNORECASE,
)


def assess_primary_binding(
    token: TokenRef,
    research: StatusResearch,
    *,
    decision_time: datetime,
) -> BindingAssessment:
    cutoff = aware_utc(decision_time, "decision_time")
    if research.token != token:
        return BindingAssessment(False, "research_token_mismatch", ())
    if research.outcome is not ResearchOutcome.FETCHED or research.tweet is None:
        return BindingAssessment(False, research.reason, ())
    tweet = research.tweet
    try:
        published = aware_utc(tweet.published_at, "tweet.published_at")
        fetched = aware_utc(tweet.fetched_at, "tweet.fetched_at")
    except (TypeError, ValueError):
        return BindingAssessment(False, "research_time_invalid", ())
    if (
        research.requested_status_id != tweet.tweet_id
        or not research.requested_handle
        or research.requested_handle.casefold() != tweet.author_handle.casefold()
    ):
        return BindingAssessment(False, "research_identity_mismatch", ())
    if published > research.lead_available_at or research.lead_available_at > fetched:
        return BindingAssessment(False, "research_time_invalid", ())
    if fetched > cutoff or research.lead_available_at > cutoff:
        return BindingAssessment(False, "status_unavailable_at_decision", ())
    addresses = tuple(sorted({item.lower() for item in _ADDRESS.findall(tweet.text)}))
    target = token.address.lower()
    if not addresses:
        return BindingAssessment(False, "target_ca_not_mentioned", ())
    if target not in addresses:
        return BindingAssessment(False, "target_ca_mismatch", addresses)
    if addresses != (target,):
        return BindingAssessment(False, "conflicting_ca_mentions", addresses)
    if not tweet.author_id:
        return BindingAssessment(False, "stable_primary_actor_id_missing", addresses)
    semantic = _positive_declaration(tweet.text, target)
    if semantic == "negative":
        return BindingAssessment(False, "target_ca_negated", addresses)
    if semantic is None:
        return BindingAssessment(False, "binding_semantics_unverified", addresses)
    digest = sha256(
        f"{token.chain}\0{target}\0{tweet.author_id}\0{tweet.tweet_id}".encode()
    ).hexdigest()
    evidence = EvidenceItem(
        evidence_id=f"x-primary-binding:{digest}",
        source=EvidenceSource.PRIMARY_ACTOR,
        role=EvidenceRole.TOKEN_BINDING,
        claim="Primary-linked X status positively declares the exact target contract",
        published_at=published,
        first_seen_at=research.lead_available_at,
        captured_at=fetched,
        token_address=target,
        source_actor=f"{tweet.author_handle}#{tweet.author_id}",
        status_id=tweet.tweet_id,
        exact_ca=True,
        independence_group=f"x-author:{tweet.author_id}",
        scope=EvidenceScope.LIVE_ELIGIBLE,
    )
    return BindingAssessment(
        True,
        "primary_actor_positive_exact_ca_binding",
        addresses,
        semantics=semantic,
        actor_basis="debot_metadata_status_lead_plus_stable_author_self_binding",
        evidence=evidence,
    )


def _positive_declaration(text: str, target: str) -> str | None:
    positions = [
        match.start() for match in _ADDRESS.finditer(text)
        if match.group().lower() == target
    ]
    positive = False
    for position in positions:
        before = text[max(0, position - 96):position]
        around = text[max(0, position - 64):position + 42 + 64]
        if _NEGATIVE.search(around):
            continue
        if _CUE_PREFIX.search(before):
            positive = True
    if positive:
        return "positive_exact_ca_declaration"
    if _NEGATIVE.search(text):
        return "negative"
    return None
