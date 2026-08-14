"""Pure conservative screen for provider and chain manipulation indicators."""

from __future__ import annotations

from decimal import Decimal

from .gmgn_public import GmgnRiskSnapshot
from .gmgn_wallet_public import GmgnWalletProfile
from .qualification import ManipulationEvidence
from .wallet_risk import has_manipulative_wallet_tag


MAX_TOP_TEN_HOLDER_RATE = Decimal("0.50")


def assess_manipulation(
    risk: GmgnRiskSnapshot,
    profiles: tuple[GmgnWalletProfile, ...],
    *,
    genuine_kol_swap: bool,
    checked_at: int,
) -> ManipulationEvidence:
    """Return WAIT inputs as None rather than treating missing checks as clean."""

    creator_links = {
        item for item in (
            risk.creator_address, risk.creator_from_address, risk.creator_fund_from,
        ) if item
    }
    wallets = {item.wallet for item in profiles}
    known_funders = tuple(item.fund_from for item in profiles if item.fund_from)
    wallet_funders = set(known_funders)
    linked = bool(creator_links & wallets or creator_links & wallet_funders)
    duplicate_funders = len(wallet_funders) < len(known_funders)
    if linked or duplicate_funders:
        shared_funding = True
    elif profiles and creator_links and len(known_funders) == len(profiles):
        shared_funding = False
    else:
        shared_funding = None
    concentration = (
        risk.top_ten_holder_rate >= MAX_TOP_TEN_HOLDER_RATE
        if risk.top_ten_holder_rate is not None else None
    )
    risky_profiles = tuple(
        profile.wallet for profile in profiles if has_manipulative_wallet_tag(profile.tags)
    )
    urls = [risk.receipt.url]
    urls.extend(receipt.url for profile in profiles for receipt in profile.receipts)
    notes = (
        f"top10_holder_rate={risk.top_ten_holder_rate}",
        f"wallet_profiles={len(profiles)}",
        f"provider_risky_wallet_profiles={len(risky_profiles)}",
        "shared_funding_is_provider-visible_only",
    )
    return ManipulationEvidence(
        checked_at=checked_at,
        genuine_kol_swap=genuine_kol_swap,
        shared_funding=shared_funding,
        concentrated_supply=concentration,
        wash_or_circular_trading=None,
        evidence_urls=tuple(dict.fromkeys(urls)),
        notes=notes,
    )
