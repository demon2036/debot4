"""Deterministic predicates for creator and community narrative paths."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping
from urllib.parse import urlparse

from .domain import ConsensusStage
from .live_context import DeBotNarrativeContext
from .models import KOL_QUALIFICATION_REASON, ResearchOutcome
from .results import LiveDossierBuild


_ADDRESS = re.compile(r"(?<![0-9a-fA-F])0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]{3,}|[\u4e00-\u9fff]{2,}")
_ALIAS = re.compile(r"^KOL-[0-9A-Fa-f]{4}$")
_OFFICIAL = re.compile(r"\b(?:official|canonical|only|real)\b|(?:官方|唯一|正版|本尊)", re.I)
_CULTURE = re.compile(
    r"\b(?:meme|mascot|culture|community|character|dog|cat|frog|panda|movement)\b"
    r"|(?:梗|吉祥物|文化|社区|角色|故事|猫|狗|青蛙|熊猫)", re.I
)
_CATALYST = re.compile(
    r"\b(?:launch(?:ed)?|announce[sd]?|release[sd]?|debut|campaign|event|listing|airdrop|mascot)\b"
    r"|(?:发布|上线|官宣|首发|空投|上市|联名|活动|事件|吉祥物)", re.I
)
_NEGATIVE = re.compile(
    r"\b(?:fake|scam|unofficial|wrong|fraud|impersonator)\b|(?:假合约|骗局|非官方|错误合约)", re.I
)
_STOP = {
    "official", "contract", "address", "token", "meme", "coin", "launch",
    "launched", "today", "this", "that", "with", "from", "meet", "community",
}


@dataclass(frozen=True, slots=True)
class NarrativeSignals:
    tweet_text: str
    description: str
    shared_terms: tuple[str, ...]
    conflict: bool
    culture: bool
    catalyst: bool
    current_kol: bool
    historical_kol: bool
    creator_leader: bool
    community_candidate: bool
    boundary_ok: bool


def analyze_context(
    base: LiveDossierBuild,
    context: DeBotNarrativeContext,
) -> NarrativeSignals:
    tweet = base.research.source_research.tweet
    tweet_text = "" if tweet is None else tweet.text.strip()
    description = (context.description or "").strip()
    shared = _theme_terms(tweet_text, description)
    boundary = base.research.current_signal
    boundary_ok = boundary is not None and (
        context.signal_id == boundary.signal_id
        and context.event_at == boundary.event_at
        and context.available_at == boundary.available_at
        and context.available_at <= base.dossier.as_of
    )
    current_kol = _current_kol(context) and boundary_ok
    historical_kol = base.research.historical_kol.qualified
    culture = len(shared) >= 2 and bool(_CULTURE.search(tweet_text + " " + description))
    social = _social_matches(context.narrative_urls, base)
    context_ok = _raw_context_consistent(context)
    no_tweet_ca = not _ADDRESS.search(tweet_text)
    community_candidate = (
        base.research.source_research.outcome is ResearchOutcome.FETCHED
        and base.research.binding.reason == "target_ca_not_mentioned"
        and no_tweet_ca
    )
    return NarrativeSignals(
        tweet_text=tweet_text,
        description=description,
        shared_terms=shared,
        conflict=_source_conflicts(tweet_text, description, base.dossier.token.address),
        culture=culture,
        catalyst=bool(_CATALYST.search(tweet_text)) and bool(shared),
        current_kol=current_kol,
        historical_kol=historical_kol,
        creator_leader=(
            base.research.binding.accepted and social and context_ok
            and bool(_OFFICIAL.search(tweet_text))
        ),
        community_candidate=community_candidate and social and context_ok and culture,
        boundary_ok=boundary_ok,
    )


def classify_stage(
    base: LiveDossierBuild,
    *,
    validation_reached: bool,
) -> ConsensusStage:
    if validation_reached:
        return ConsensusStage.VALIDATION
    return (
        ConsensusStage.DISCOVERY
        if base.research.source_research.tweet is not None
        else ConsensusStage.UNRESOLVED
    )


def classification_thesis(
    context: DeBotNarrativeContext,
    shared: tuple[str, ...],
    *,
    contradicted: bool = False,
) -> str:
    label = context.token_name or context.token_symbol or context.token_address
    if contradicted:
        return f"{label} has contradictory narrative-to-token evidence"
    subject = ", ".join(shared[:5]) or "an unresolved meme narrative"
    return f"{label} is associated with {subject}; canonicality is separately classified"


def _current_kol(context: DeBotNarrativeContext) -> bool:
    aliases = context.wallet_aliases
    return (
        context.signal_kind == "kol"
        and context.group_name.casefold().startswith("kol#")
        and context.kol_buy_qualified
        and context.kol_buy_reason == KOL_QUALIFICATION_REASON
        and len(aliases) >= 3
        and len(set(aliases)) == len(aliases)
        and all(_ALIAS.fullmatch(item) for item in aliases)
    )


def _social_matches(urls: tuple[str, ...], base: LiveDossierBuild) -> bool:
    tweet = base.research.source_research.tweet
    if tweet is None:
        return False
    handle = tweet.author_handle.casefold()
    hosts = {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}
    for url in urls:
        parsed = urlparse(url)
        parts = tuple(item for item in parsed.path.split("/") if item)
        if parsed.hostname in hosts and parts and parts[0].casefold() == handle:
            return True
    return False


def _raw_context_consistent(context: DeBotNarrativeContext) -> bool:
    raw = context.raw_context
    profile = raw.get("profile") if isinstance(raw, Mapping) else None
    social = raw.get("social") if isinstance(raw, Mapping) else None
    if not isinstance(profile, Mapping) or not isinstance(social, Mapping):
        return False
    name = str(profile.get("name") or "").strip().casefold()
    symbol = str(profile.get("symbol") or "").strip().casefold()
    expected_name = (context.token_name or "").strip().casefold()
    expected_symbol = (context.token_symbol or "").strip().casefold()
    social_description = str(social.get("description") or "").strip()
    return bool(
        expected_name and expected_symbol and context.description
        and name == expected_name and symbol == expected_symbol
        and social_description == context.description
    )


def _source_conflicts(primary: str, description: str, target: str) -> bool:
    text = primary + " " + description
    addresses = {item.lower() for item in _ADDRESS.findall(text)}
    return bool(_NEGATIVE.search(text) or addresses - {target})


def _theme_terms(primary: str, description: str) -> tuple[str, ...]:
    def terms(text: str) -> set[str]:
        return {
            item.casefold() for item in _WORD.findall(_ADDRESS.sub(" ", text))
            if item.casefold() not in _STOP
        }
    return tuple(sorted(terms(primary).intersection(terms(description))))
