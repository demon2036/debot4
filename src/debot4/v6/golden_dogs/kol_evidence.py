"""Immutable reviewed KOL wallet attribution without trading conclusions."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re


_ADDRESS = re.compile(r"0x[0-9a-f]{40}")
_TX_HASH = re.compile(r"0x[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class WalletAttribution:
    handle: str
    chain: str
    wallet: str
    token_address: str
    token_symbol: str
    disclosure_tweet_id: str
    disclosed_at: int
    disclosed_balance_approx: Decimal
    transfer_tx: str
    transfer_at: int
    transfer_amount: Decimal
    explorer_address_url: str
    explorer_transfer_url: str
    attribution_class: str
    account_type: str

    def __post_init__(self) -> None:
        wallet = self.wallet.casefold()
        token = self.token_address.casefold()
        transaction = self.transfer_tx.casefold()
        if not _ADDRESS.fullmatch(wallet) or not _ADDRESS.fullmatch(token):
            raise ValueError("wallet evidence requires exact EVM addresses")
        if not _TX_HASH.fullmatch(transaction):
            raise ValueError("wallet evidence requires an exact transaction hash")
        if min(self.disclosed_balance_approx, self.transfer_amount) <= 0:
            raise ValueError("wallet evidence amounts must be positive")
        if self.transfer_at > self.disclosed_at:
            raise ValueError("attribution transfer must predate the disclosure")
        object.__setattr__(self, "wallet", wallet)
        object.__setattr__(self, "token_address", token)
        object.__setattr__(self, "transfer_tx", transaction)

    @property
    def disclosure_url(self) -> str:
        return f"https://x.com/{self.handle}/status/{self.disclosure_tweet_id}"


KOL_WALLET_ATTRIBUTIONS = (
    WalletAttribution(
        handle="kenjiquest",
        chain="robinhood",
        wallet="0x2ca0ef05ec3383944f40c4ac2e9346c4fb441e31",
        token_address="0xe724485732d12c3ec6dba2176f55338eb2124ba3",
        token_symbol="iHOOD",
        disclosure_tweet_id="2084080681903337928",
        disclosed_at=1785718529,
        disclosed_balance_approx=Decimal("156000000"),
        transfer_tx="0xb4d8b88fdee6093c0286e75b37606933056f0753483b1a8837612da4ca1774dc",
        transfer_at=1785472492,
        transfer_amount=Decimal("156947093.381947019125647259"),
        explorer_address_url=(
            "https://robinhoodchain.blockscout.com/address/"
            "0x2ca0ef05ec3383944f40c4ac2e9346c4fb441e31"
        ),
        explorer_transfer_url=(
            "https://robinhoodchain.blockscout.com/tx/"
            "0xb4d8b88fdee6093c0286e75b37606933056f0753483b1a8837612da4ca1774dc"
        ),
        attribution_class="self_disclosed_suffix_exact_balance_match",
        account_type="eip7702_delegated_account",
    ),
)
