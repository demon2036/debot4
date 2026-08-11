from debot4.v6.narrative.actor_catalog import DEFAULT_ACTOR_CATALOG
from debot4.v6.narrative.actor_registry import DEFAULT_ACTOR_REGISTRY
from debot4.v6.narrative.actors import ActorCapability, ActorTier


REQUIRED_HANDLES = {
    "yeonwoo1102",
    "sencrazy_1",
    "nina_rong",
    "2442lll",
    "blknoiz06",
    "cryptodevinl",
    "hexiecs",
    "btc2ai",
    "ddakbbam1",
    "kenjiquest",
    "ageullo",
    "0xblackluke",
    "golocojp",
    "0xcryptowizard",
    "0xmmu",
    "btcold8",
    "agnesrium",
    "robinhoodalphas",
    "seyong",
    "theindexfi",
    "pumpfun",
    "a1lon9",
    "raydium",
    "jupiterexchange",
    "bonkfun",
    "bonk_inu",
    "fourdotmemezh",
    "bagsapp",
    "elonmusk",
    "cz_binance",
    "sunapooh67",
    "jtitordemon2036",
}


def test_catalog_has_broad_reviewed_cross_region_coverage() -> None:
    handles = {item.handle.casefold() for item in DEFAULT_ACTOR_CATALOG}

    assert len(DEFAULT_ACTOR_CATALOG) >= 60
    assert REQUIRED_HANDLES <= handles
    assert {region for item in DEFAULT_ACTOR_CATALOG for region in item.regions} >= {
        "china", "korea", "japan", "us", "global"
    }
    assert {chain for item in DEFAULT_ACTOR_CATALOG for chain in item.ecosystems} >= {
        "bsc", "solana", "ethereum", "base", "robinhood", "x"
    }


def test_catalog_identity_metadata_and_evidence_are_complete_and_unique() -> None:
    handles = [item.handle.casefold() for item in DEFAULT_ACTOR_CATALOG]
    ids = [item.author_ids[0] for item in DEFAULT_ACTOR_CATALOG]

    assert len(handles) == len(set(handles))
    assert len(ids) == len(set(ids))
    for item in DEFAULT_ACTOR_CATALOG:
        assert item.display_name and item.role and item.basis
        assert item.author_ids and item.evidence_urls
        assert item.evidence_urls[0].casefold() == f"https://x.com/{item.handle}".casefold()


def test_kols_are_clues_only_and_cannot_bind_a_contract() -> None:
    for item in DEFAULT_ACTOR_CATALOG:
        if item.tier is not ActorTier.PROPAGATION_KOL:
            continue
        assert item.capabilities == (ActorCapability.PROPAGATE,)
        actor = DEFAULT_ACTOR_REGISTRY.resolve(item.handle)
        assert actor.is_propagation_only
        assert not actor.can_bind_token


def test_yeon_alias_and_stable_identity_prevent_ambiguous_name_miss() -> None:
    yeon = DEFAULT_ACTOR_REGISTRY.resolve("yeon")

    assert yeon.handle == "yeonwoo1102"
    assert yeon.actor_id == "x:yeonwoo1102"
    assert yeon.display_name == "Yeon"
    assert yeon.languages == ("ko", "en")
    assert "Yndegen" in yeon.telegram_channels
    assert yeon.telegram_public_channels == ("Yndegen",)
    assert DEFAULT_ACTOR_REGISTRY.resolve_telegram("@Yndegen") == yeon


def test_priority_kols_have_exact_authored_status_evidence() -> None:
    required = {
        "yeonwoo1102", "sencrazy_1", "nina_rong", "2442lll",
        "cryptodevinl", "hexiecs", "btc2ai", "blknoiz06",
        "ageullo", "0xblackluke", "golocojp", "0xcryptowizard",
        "0xmmu", "btcold8", "agnesrium", "robinhoodalphas",
        "a1lon9", "jupiterexchange", "meteoraag", "bonkfun",
        "bonk_inu", "fourdotmemezh", "bagsapp", "believeapp", "moonshot",
    }

    for item in DEFAULT_ACTOR_CATALOG:
        if item.handle.casefold() not in required:
            continue
        assert "exact authored status" in item.basis
        assert len(item.evidence_urls) >= 2
        assert "/status/" in item.evidence_urls[1]


def test_rejected_noise_accounts_are_not_monitored() -> None:
    handles = {item.handle.casefold() for item in DEFAULT_ACTOR_CATALOG}

    assert {
        "jianfengsh68965",
        "aye5098",
        "yummmycrypotato",
        "cryptoenact",
        "spiderman_rich",
        "00q__",
    }.isdisjoint(handles)


def test_only_reviewed_public_telegram_channels_enter_automatic_monitoring() -> None:
    public = {
        channel.casefold()
        for item in DEFAULT_ACTOR_CATALOG
        for channel in item.telegram_public_channels
    }

    assert public == {
        "altcoinsherpata", "emperorcoin", "msnft0", "pote_korea", "yndegen",
    }
    assert DEFAULT_ACTOR_REGISTRY.resolve_telegram("D11111D1") is None
    assert DEFAULT_ACTOR_REGISTRY.resolve("CryptoDevinL").telegram_channels == (
        "D11111D1",
    )


def test_personal_session_can_monitor_reviewed_non_public_channel() -> None:
    leo = DEFAULT_ACTOR_REGISTRY.resolve("ezeroho8245")

    assert leo.telegram_public_channels == ()
    assert leo.telegram_realtime_channels == ("LeoMaster_memes",)
    assert DEFAULT_ACTOR_REGISTRY.resolve_telegram("@LeoMaster_memes") == leo


def test_profile_evidence_never_expands_status_trust_boundary() -> None:
    binance = DEFAULT_ACTOR_REGISTRY.resolve("binance")

    assert DEFAULT_ACTOR_REGISTRY.permits(
        binance,
        "binance",
        "877807935493033984",
        "https://x.com/binance/status/1234567",
        "example",
    )
    assert not DEFAULT_ACTOR_REGISTRY.permits(
        binance,
        "binance",
        "877807935493033984",
        "https://www.binance.com/status/1234567",
        "example",
    )


def test_operator_canary_has_no_narrative_or_trading_authority() -> None:
    canary = DEFAULT_ACTOR_REGISTRY.resolve("jtitordemon2036")

    assert canary.actor_id == "x:jtitordemon2036"
    assert canary.display_name == "john titor"
    assert canary.priority == 1
    assert canary.monitor_x is True
    assert canary.monitor_reposts is True
    assert canary.capabilities == ()
