"""Shared immutable observations for catalyst-to-mint regression tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from debot4.v6.debot.ranks_models import RankSnapshot
from debot4.v6.narrative.catalyst_mint import CatalystMintMatch
from debot4.v6.narrative.mint_location import BSC_LOG_SOURCE, MintLocation
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
BUDUJIN_STATUS = "2088277816865604031"
BUDUJIN_POST_AT = datetime(2026, 8, 14, 14, 53, 24, tzinfo=UTC)
BUDUJIN_MINT_AT = BUDUJIN_POST_AT + timedelta(seconds=12)
BUDUJIN_OBSERVED_AT = BUDUJIN_POST_AT + timedelta(seconds=13)
BUDUJIN_DELIVERED_AT = BUDUJIN_POST_AT + timedelta(seconds=14)
BUDUJIN_CA = "0xf3e36b6935f403b205d4898519c46809c7447777"
BUDUJIN_RAW_CA = "0xcbbe5d64312d137c2fa4152ced4bbc24493e7777"


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
    stage: str = "new",
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
        exact_ca, stage, fetched_at or created_at + timedelta(seconds=1),
        "bBroker", "bBroker", 0, (), Decimal("0"), Decimal("5000.67"),
        stage == "completed", created_at, "flap", None, urls,
    )


def budujin_post() -> XPost:
    return XPost(
        BUDUJIN_STATUS,
        "flapdotsh",
        "Seed Alpha. Soon on Flap.sh. 这个币，有点不对劲 👀",
        BUDUJIN_POST_AT,
        BUDUJIN_POST_AT + timedelta(seconds=2),
    )


def budujin_mint(
    *, exact_ca: str = BUDUJIN_CA, linked: bool = True,
) -> RankSnapshot:
    urls = (
        (f"https://x.com/flapdotsh/status/{BUDUJIN_STATUS}",)
        if linked else ()
    )
    created = (
        BUDUJIN_MINT_AT
        if linked else BUDUJIN_POST_AT - timedelta(minutes=3)
    )
    return RankSnapshot(
        exact_ca, "completing", BUDUJIN_OBSERVED_AT,
        "SEED ALPHA", "不对劲", 0, (), Decimal("0"), Decimal("5000"),
        False, created, "flap", None, urls,
    )


def budujin_match() -> CatalystMintMatch:
    value = CatalystMintMatch.from_observations(
        budujin_post(), budujin_mint()
    )
    assert value is not None
    return value


def budujin_raw_location() -> MintLocation:
    created = BUDUJIN_POST_AT - timedelta(minutes=3)
    return MintLocation(
        exact_ca=BUDUJIN_RAW_CA,
        source=BSC_LOG_SOURCE,
        observed_at=created + timedelta(seconds=2),
        created_at=created,
        transaction_hash="0x" + "1" * 64,
        block_number=115_907_406,
        block_hash="0x" + "2" * 64,
        transaction_index=1,
    )
