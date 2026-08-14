"""Translate exact catalyst-mint evidence into a focused research request."""

from __future__ import annotations

from .catalyst_mint import CatalystMintMatch
from .passive_trigger import PassiveNarrativeTrigger


def passive_trigger_from_catalyst_mint(
    match: CatalystMintMatch,
) -> PassiveNarrativeTrigger:
    delay = match.mint_delay_seconds
    fdv = (
        "unknown" if match.provider_fdv_usd is None
        else f"${format(match.provider_fdv_usd, 'f')}"
    )
    description = match.token_description or "unknown"
    anomaly = (
        "Deterministic new-mint binding: DeBot listed exact CA "
        f"{match.exact_ca}; its token metadata contains X status ID "
        f"{match.catalyst_tweet_id}, exactly matching the monitored post by "
        f"@{match.catalyst_author}. The post was published at "
        f"{match.catalyst_created_at.isoformat()}, and the token was created at "
        f"{match.token_created_at.isoformat()} ({delay:+.3f}s later). "
        f"Launchpad={match.launchpad or 'unknown'}; provider FDV at first relevant "
        f"observation={fdv}; token description={description}. This proves an "
        "asset-to-post metadata reference only; it is not proof of endorsement, "
        "price causality, safety, profitability, or trade authority."
    )
    return PassiveNarrativeTrigger(
        exact_ca=match.exact_ca,
        signal_id=match.match_id,
        observed_at=match.observed_at,
        token_name=match.token_name,
        token_symbol=match.token_symbol,
        anomaly=anomaly,
        social_urls=(match.token_status_url,),
    )
