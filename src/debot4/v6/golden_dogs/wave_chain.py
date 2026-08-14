"""Pure time-window summaries for chain buys around replayed market waves."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ChainBuy:
    timestamp: int
    transaction_hash: str
    wallet: str
    amount_usd: Decimal
    x_handle: str | None
    tags: tuple[str, ...]
    rpc_receipt_sha256: str
    clean: bool

    def __post_init__(self) -> None:
        if self.timestamp <= 0 or self.amount_usd < 0:
            raise ValueError("invalid chain buy")
        if not self.transaction_hash.startswith("0x"):
            raise ValueError("invalid transaction hash")
        if not self.wallet.startswith("0x"):
            raise ValueError("invalid wallet")


@dataclass(frozen=True, slots=True)
class ChainActivity:
    start: int
    end_exclusive: int
    tagged_buy_count: int
    tagged_wallet_count: int
    tagged_amount_usd: Decimal
    clean_buy_count: int
    clean_wallet_count: int
    clean_amount_usd: Decimal
    earliest_tagged: ChainBuy | None
    earliest_clean: ChainBuy | None
    largest_clean: ChainBuy | None

    def __post_init__(self) -> None:
        if not 0 < self.start < self.end_exclusive:
            raise ValueError("invalid activity interval")


def summarize_chain_activity(
    buys: Iterable[ChainBuy], start: int, end_exclusive: int,
) -> ChainActivity:
    """Summarize tagged and reviewed-clean buys in one half-open interval."""

    if not 0 < start < end_exclusive:
        raise ValueError("invalid activity interval")
    selected = tuple(sorted(
        (buy for buy in buys if start <= buy.timestamp < end_exclusive),
        key=lambda buy: (buy.timestamp, buy.transaction_hash),
    ))
    clean = tuple(buy for buy in selected if buy.clean)
    return ChainActivity(
        start=start,
        end_exclusive=end_exclusive,
        tagged_buy_count=len(selected),
        tagged_wallet_count=len({buy.wallet.casefold() for buy in selected}),
        tagged_amount_usd=sum((buy.amount_usd for buy in selected), Decimal(0)),
        clean_buy_count=len(clean),
        clean_wallet_count=len({buy.wallet.casefold() for buy in clean}),
        clean_amount_usd=sum((buy.amount_usd for buy in clean), Decimal(0)),
        earliest_tagged=selected[0] if selected else None,
        earliest_clean=clean[0] if clean else None,
        largest_clean=max(clean, key=lambda buy: buy.amount_usd) if clean else None,
    )
