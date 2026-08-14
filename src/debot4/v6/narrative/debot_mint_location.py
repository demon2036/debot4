"""Map DeBot's new-stage provider model into raw Exact CA evidence."""

from __future__ import annotations

from ..debot.ranks_models import RankSnapshot
from .mint_location import DEBOT_NEW_SOURCE, MintLocation


def location_from_debot(snapshot: RankSnapshot) -> MintLocation:
    """Keep every exact new-feed CA, even without metadata or creation time."""

    if snapshot.stage != "new":
        raise ValueError("mint location requires a DeBot new-stage snapshot")
    return MintLocation(
        exact_ca=snapshot.token_address,
        source=DEBOT_NEW_SOURCE,
        observed_at=snapshot.fetched_at,
        created_at=snapshot.created_at,
        launchpad=snapshot.launchpad,
        token_name=snapshot.name,
        token_symbol=snapshot.symbol,
        provider_fdv_usd=snapshot.provider_fdv_usd,
        social_urls=snapshot.social_urls,
    )
