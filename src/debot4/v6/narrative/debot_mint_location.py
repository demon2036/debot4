"""Map every DeBot launch stage into raw exact-CA evidence."""

from __future__ import annotations

from ..debot.ranks_models import RankSnapshot
from .mint_location import DEBOT_STAGE_SOURCES, MintLocation


def location_from_debot(snapshot: RankSnapshot) -> MintLocation:
    """Keep every stage-specific CA, even without metadata or creation time."""

    source = DEBOT_STAGE_SOURCES.get(snapshot.stage)
    if source is None:
        raise ValueError("mint location requires a known DeBot ranks stage")
    return MintLocation(
        exact_ca=snapshot.token_address,
        source=source,
        observed_at=snapshot.fetched_at,
        created_at=snapshot.created_at,
        launchpad=snapshot.launchpad,
        token_name=snapshot.name,
        token_symbol=snapshot.symbol,
        provider_fdv_usd=snapshot.provider_fdv_usd,
        social_urls=snapshot.social_urls,
    )
