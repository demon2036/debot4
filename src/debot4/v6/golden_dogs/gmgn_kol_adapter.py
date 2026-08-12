"""Map GMGN-tagged buys and independent RPC checks to KOL-buy evidence."""

from __future__ import annotations

from .bsc_rpc import VerifiedTokenSwap
from .gmgn_public import GmgnTaggedTrade
from .qualification import KolWalletTrade, ProviderKolBuy


def provider_buy_from_gmgn(
    trade: GmgnTaggedTrade,
    verified_swap: VerifiedTokenSwap,
    *,
    provider_url: str,
) -> ProviderKolBuy:
    if trade.event != "buy":
        raise ValueError("GMGN KOL evidence must be a buy")
    if (
        trade.wallet != verified_swap.wallet
        or trade.token_address != verified_swap.token_address
        or trade.transaction_hash != verified_swap.transaction_hash
        or trade.timestamp != verified_swap.block_timestamp
    ):
        raise ValueError("GMGN trade and BSC RPC evidence do not match")
    if not provider_url.startswith("https://gmgn.ai/"):
        raise ValueError("GMGN evidence URL is invalid")
    alias = trade.x_handle or trade.name or trade.wallet
    return ProviderKolBuy(
        provider="gmgn",
        chain="bsc",
        token_address=trade.token_address,
        signal_id=trade.transaction_hash,
        provider_event_at=trade.timestamp,
        provider_url=provider_url,
        trades=(
            KolWalletTrade(
                provider_alias=alias,
                bought_at=trade.timestamp,
                volume_usd=trade.amount_usd,
                token_amount=trade.token_amount,
                wallet=trade.wallet,
                transaction_hash=trade.transaction_hash,
                swap_verified=True,
                risk_tags=trade.tags,
            ),
        ),
    )
