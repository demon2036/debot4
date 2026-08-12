"""Validated authority-wallet actions; transactions are evidence, not orders."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from ..explosion import ExplosionCategory, ExplosionEvent


_EVM_CA = re.compile(r"0x[a-f0-9]{40}")
_TX = re.compile(r"0x[a-f0-9]{64}")


class WalletAction(str, Enum):
    FIRST_BUY = "first_buy"
    CREATOR_FEE_RECEIVED = "creator_fee_received"
    LIQUIDITY_ADDED = "liquidity_added"
    MIGRATED = "migrated"
    CROSSED_CHAIN = "crossed_chain"
    BUYBACK = "buyback"
    BURN = "burn"


@dataclass(frozen=True, slots=True)
class AuthorityWalletAction:
    chain: str
    token_address: str
    wallet_address: str
    wallet_role: str
    action: WalletAction
    tx_hash: str
    block_number: int
    log_index: int
    occurred_at: datetime
    first_seen_at: datetime
    source_url: str
    evidence_hash: str

    def __post_init__(self) -> None:
        action = WalletAction(self.action)
        token = self.token_address.strip().casefold()
        wallet = self.wallet_address.strip().casefold()
        tx_hash = self.tx_hash.strip().casefold()
        if not _EVM_CA.fullmatch(token) or not _EVM_CA.fullmatch(wallet):
            raise ValueError("authority wallet action requires exact addresses")
        if not _TX.fullmatch(tx_hash) or self.block_number < 0 or self.log_index < 0:
            raise ValueError("authority wallet transaction receipt is invalid")
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "token_address", token)
        object.__setattr__(self, "wallet_address", wallet)
        object.__setattr__(self, "tx_hash", tx_hash)

    def event(self) -> ExplosionEvent:
        return ExplosionEvent(
            category=ExplosionCategory.AUTHORITY_WALLET,
            subtype=self.action.value,
            occurred_at=self.occurred_at,
            first_seen_at=self.first_seen_at,
            subject=self.wallet_address,
            actor_id=self.wallet_address,
            actor_role=self.wallet_role,
            source_url=self.source_url,
            evidence_hash=self.evidence_hash,
            previous={},
            current={
                "tx_hash": self.tx_hash,
                "block_number": self.block_number,
                "log_index": self.log_index,
            },
            confidence="verified",
            chain=self.chain,
            token_address=self.token_address,
        )
