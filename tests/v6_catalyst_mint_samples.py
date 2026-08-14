"""Shared immutable observations for catalyst-to-mint regression tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.x.models import XPost


UTC = timezone.utc
BBROKER_CA = "0xf1969f437fe3c485468fb17b0d9861c24dcd7777"
BBROKER_STATUS = "2087894611733922300"
BBROKER_POST_AT = datetime(2026, 8, 13, 13, 30, 41, tzinfo=UTC)
BBROKER_MINT_AT = datetime(2026, 8, 13, 13, 32, 2, tzinfo=UTC)
FLAP_CA = "0x6d2137fe9113d28135edfb274cb0d94447497777"
FLAP_STATUS = "2088104486892138899"
FLAP_POST_AT = datetime(2026, 8, 14, 3, 24, 39, tzinfo=UTC)
FLAP_MINT_AT = datetime(2026, 8, 14, 3, 24, 55, tzinfo=UTC)


def catalyst_post(
    status_id: str = BBROKER_STATUS,
    created_at: datetime = BBROKER_POST_AT,
    fetched_at: datetime | None = None,
) -> XPost:
    return XPost(
        status_id,
        "flapdotsh",
        "Introducing the Flap bBroker Vault on BNB Chain, powered by bStocks.",
        created_at,
        fetched_at or created_at + timedelta(seconds=5),
    )


def mint_snapshot(
    *,
    exact_ca: str = BBROKER_CA,
    status_id: str = BBROKER_STATUS,
    created_at: datetime = BBROKER_MINT_AT,
    fetched_at: datetime | None = None,
    social_urls: tuple[str, ...] | None = None,
) -> RankSnapshot:
    urls = (
        (
            f"https://x.com/flapdotsh/status/{status_id}",
            "https://availablepools.com",
        )
        if social_urls is None else social_urls
    )
    return RankSnapshot(
        exact_ca, "new", fetched_at or created_at + timedelta(seconds=1),
        "bBroker", "bBroker", 0, (), Decimal("0"), Decimal("5000.67"),
        False, created_at, "flap", None, urls,
    )
