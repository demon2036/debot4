from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from debot4.v6.golden_dogs.models import Candle, EvidenceReceipt, MarketTrace
from debot4.v6.golden_dogs.qualification import (
    KolWalletTrade,
    ManipulationEvidence,
    ProviderKolBuy,
    Verdict,
    qualify_golden_dog,
)
from debot4.v6.golden_dogs.rules import analyze_market


CA = "0x" + "a" * 40
RECEIPT = EvidenceReceipt(
    "test_json",
    "https://example.test/evidence",
    1,
    "0" * 64,
)


def seed():
    from debot4.v6.golden_dogs.models import TokenSeed

    return TokenSeed(
        chain="bsc",
        address=CA,
        name="Story Dog",
        symbol="DOG",
        launchpad="four_meme",
        created_at=10,
        creator_address="0x" + "b" * 40,
        rank_supply=Decimal("1000000000"),
        current_kols=1,
        max_kols=3,
        social_urls=(),
        discovered_sources=("four_meme",),
    )


def observation():
    trace = MarketTrace(
        (
            Candle(10, Decimal("0.0001"), Decimal("0.0001"), Decimal("0.0001"), Decimal("0.0001"), Decimal("1")),
            Candle(20, Decimal("0.0006"), Decimal("0.0006"), Decimal("0.0006"), Decimal("0.0006"), Decimal("1")),
        ),
        Decimal("1000000000"),
        18,
        RECEIPT,
    )
    return analyze_market(
        seed(), trace, window_start=1, window_end_exclusive=100,
    )


def provider_buy() -> ProviderKolBuy:
    return ProviderKolBuy(
        provider="debot",
        chain="bsc",
        token_address=CA,
        signal_id="signal-1",
        provider_event_at=30,
        provider_url=f"https://debot.ai/token/bsc/{CA}",
        trades=(
            KolWalletTrade(
                provider_alias="KOL-abcd",
                bought_at=19,
                volume_usd=Decimal("123"),
                token_amount=Decimal("456"),
                wallet="0x" + "c" * 40,
                transaction_hash="0x" + "d" * 64,
                swap_verified=True,
            ),
        ),
    )


def clean_screen(**changes: bool | None) -> ManipulationEvidence:
    values = {
        "genuine_kol_swap": True,
        "shared_funding": False,
        "concentrated_supply": False,
        "wash_or_circular_trading": False,
    }
    values.update(changes)
    return ManipulationEvidence(
        checked_at=40,
        evidence_urls=("https://bscscan.com/tx/" + "1" * 64,),
        **values,
    )


def test_all_three_independent_gates_are_required() -> None:
    result = qualify_golden_dog(observation(), (provider_buy(),), clean_screen())
    assert result.verdict is Verdict.PASS
    assert result.market.verdict is Verdict.PASS
    assert result.kol_buy.verdict is Verdict.PASS
    assert result.causal_timing.verdict is Verdict.PASS
    assert result.manipulation.verdict is Verdict.PASS


def test_aggregate_kol_rank_count_is_pending_not_buy_evidence() -> None:
    result = qualify_golden_dog(observation(), manipulation=clean_screen())
    assert result.verdict is Verdict.WAIT
    assert result.kol_buy.reasons == ("aggregate_kol_count_is_not_buy_evidence",)


def test_provider_assertion_without_chain_screen_stays_pending() -> None:
    result = qualify_golden_dog(observation(), (provider_buy(),))
    assert result.verdict is Verdict.WAIT
    assert result.kol_buy.verdict is Verdict.PASS
    assert result.manipulation.verdict is Verdict.WAIT


def test_provider_buy_without_rpc_verification_stays_pending() -> None:
    trade = replace(
        provider_buy().trades[0],
        wallet=None,
        transaction_hash=None,
        swap_verified=None,
    )
    result = qualify_golden_dog(
        observation(), (replace(provider_buy(), trades=(trade,)),), clean_screen(),
    )
    assert result.verdict is Verdict.WAIT
    assert result.kol_buy.reasons == ("provider_kol_buy_needs_chain_verification",)


def test_post_peak_kol_buy_is_not_a_causal_hit() -> None:
    late = replace(
        provider_buy(),
        trades=(replace(provider_buy().trades[0], bought_at=21),),
    )
    result = qualify_golden_dog(observation(), (late,), clean_screen())
    assert result.verdict is Verdict.PASS
    assert result.kol_buy.reasons == ("verified_provider_kol_buy:debot",)
    assert result.causal_timing.verdict is Verdict.REJECT
    assert result.causal_timing.reasons == ("provider_kol_buy_is_post_peak_only",)


def test_wash_trader_tag_rejects_kol_buy() -> None:
    wash = replace(
        provider_buy(),
        trades=(replace(provider_buy().trades[0], risk_tags=("wash_trader",)),),
    )
    result = qualify_golden_dog(observation(), (wash,), clean_screen())
    assert result.verdict is Verdict.REJECT
    assert result.kol_buy.reasons == ("kol_buy_has_manipulation_tag",)


def test_other_provider_manipulation_tags_also_reject_kol_buy() -> None:
    sybil = replace(
        provider_buy(),
        trades=(replace(provider_buy().trades[0], risk_tags=("sybil",)),),
    )
    result = qualify_golden_dog(observation(), (sybil,), clean_screen())

    assert result.verdict is Verdict.REJECT
    assert result.kol_buy.reasons == ("kol_buy_has_manipulation_tag",)


def test_manipulation_indicator_rejects_otherwise_valid_candidate() -> None:
    result = qualify_golden_dog(
        observation(),
        (provider_buy(),),
        clean_screen(shared_funding=True),
    )
    assert result.verdict is Verdict.REJECT
    assert result.manipulation.reasons == (
        "deployer_kol_or_wallets_share_funding",
    )


def test_complete_provider_search_can_reject_missing_buy() -> None:
    no_aggregate = replace(observation(), current_kols=0, max_kols=0)
    result = qualify_golden_dog(
        no_aggregate,
        manipulation=clean_screen(),
        kol_coverage_complete=True,
    )
    assert result.verdict is Verdict.REJECT
    assert result.kol_buy.reasons == ("no_debot_or_gmgn_kol_buy",)


def test_swap_verdict_cannot_be_claimed_without_chain_locators() -> None:
    try:
        KolWalletTrade(
            provider_alias="KOL-abcd",
            bought_at=1,
            volume_usd=Decimal("1"),
            token_amount=Decimal("1"),
            swap_verified=True,
        )
    except ValueError as exc:
        assert "exact wallet and transaction" in str(exc)
    else:
        raise AssertionError("missing chain locators were accepted")
