"""Evidence factories for categorical narrative classification."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256

from .domain import EvidenceRole, EvidenceScope, EvidenceSource
from .evidence import EvidenceItem
from .live_context import DeBotNarrativeContext
from .results import LiveDossierBuild


def debot_item(
    context: DeBotNarrativeContext,
    cutoff: datetime,
    role: EvidenceRole,
    claim: str,
    *,
    source: EvidenceSource = EvidenceSource.DEBOT,
) -> EvidenceItem:
    digest = sha256(f"{context.signal_id}\0{role.value}".encode()).hexdigest()
    return EvidenceItem(
        f"debot-narrative:{digest}", source, role, claim,
        context.event_at, context.available_at, max(cutoff, context.available_at),
        context.token_address, context.group_name, context.signal_id, True,
        f"debot-signal:{context.signal_id}", EvidenceScope.LIVE_ELIGIBLE,
    )


def primary_item(
    base: LiveDossierBuild,
    role: EvidenceRole,
    claim: str,
) -> EvidenceItem | None:
    tweet = base.research.source_research.tweet
    if tweet is None:
        return None
    digest = sha256(f"{tweet.tweet_id}\0{role.value}".encode()).hexdigest()
    return EvidenceItem(
        f"x-narrative:{digest}", EvidenceSource.PRIMARY_ACTOR, role, claim,
        tweet.published_at, base.research.source_research.lead_available_at,
        tweet.fetched_at, "", f"{tweet.author_handle}#{tweet.author_id}",
        tweet.tweet_id, False, f"x-author:{tweet.author_id}",
        EvidenceScope.LIVE_ELIGIBLE,
    )


def current_capital_item(
    context: DeBotNarrativeContext,
    cutoff: datetime,
) -> EvidenceItem:
    return debot_item(
        context,
        cutoff,
        EvidenceRole.CAPITAL_CONFIRMATION,
        "The current DeBot wave contains a qualified windowed KOL BUY",
        source=EvidenceSource.KOL,
    )
