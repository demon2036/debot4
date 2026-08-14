"""Provider-neutral evidence that an exact BSC token address now exists."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import re
from types import MappingProxyType

from ..identity import bsc_address, utc_datetime


DEBOT_NEW_SOURCE = "debot_new"
DEBOT_COMPLETING_SOURCE = "debot_completing"
DEBOT_COMPLETED_SOURCE = "debot_completed"
DEBOT_STAGE_SOURCES = MappingProxyType({
    "new": DEBOT_NEW_SOURCE,
    "completing": DEBOT_COMPLETING_SOURCE,
    "completed": DEBOT_COMPLETED_SOURCE,
})
BSC_LOG_SOURCE = "bsc_zero_transfer_log"
MINT_LOCATION_SOURCES = frozenset((*DEBOT_STAGE_SOURCES.values(), BSC_LOG_SOURCE))
_HASH = re.compile(r"0x[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class MintLocation:
    """Raw location evidence; it never implies catalyst ownership or a trade."""

    exact_ca: str
    source: str
    observed_at: datetime
    created_at: datetime | None
    launchpad: str | None = None
    token_name: str | None = None
    token_symbol: str | None = None
    provider_fdv_usd: Decimal | None = None
    social_urls: tuple[str, ...] = ()
    transaction_hash: str | None = None
    block_number: int | None = None
    block_hash: str | None = None
    transaction_index: int | None = None
    factory_address: str | None = None
    location_id: str = field(init=False)
    authorizes_trade: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        exact_ca = bsc_address(self.exact_ca)
        source = str(self.source).strip().casefold()
        if source not in MINT_LOCATION_SOURCES:
            raise ValueError("unsupported mint location source")
        observed = utc_datetime(self.observed_at)
        created = None if self.created_at is None else utc_datetime(self.created_at)
        if created is not None and observed + timedelta(seconds=30) < created:
            raise ValueError("mint observation predates its source event")
        launchpad = _text(self.launchpad, 80)
        name = _text(self.token_name, 160)
        symbol = _text(self.token_symbol, 80)
        urls = _urls(self.social_urls)
        fdv = self.provider_fdv_usd
        if fdv is not None and (
            not isinstance(fdv, Decimal) or not fdv.is_finite() or fdv < 0
        ):
            raise ValueError("provider FDV must be a finite non-negative Decimal")
        transaction_hash = _optional_hash(self.transaction_hash)
        block_hash = _optional_hash(self.block_hash)
        factory = (
            None if self.factory_address is None
            else bsc_address(self.factory_address)
        )
        chain_position = (
            transaction_hash, self.block_number, block_hash,
            self.transaction_index,
        )
        if source == BSC_LOG_SOURCE:
            if any(item is None for item in chain_position) or created is None:
                raise ValueError("chain mint location requires complete log evidence")
            if factory is not None:
                raise ValueError("zero-transfer evidence cannot infer a factory")
            if any(
                isinstance(item, bool)
                or not isinstance(item, int)
                or item < 0
                for item in (self.block_number, self.transaction_index)
            ):
                raise ValueError("chain mint position must be non-negative")
            reference = (
                f"{block_hash[2:]}-{transaction_hash[2:]}-{exact_ca[2:]}"
            )
        else:
            if any(item is not None for item in (*chain_position, factory)):
                raise ValueError("DeBot mint location cannot contain chain log fields")
            reference = exact_ca[2:]
        object.__setattr__(self, "exact_ca", exact_ca)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "launchpad", launchpad)
        object.__setattr__(self, "token_name", name)
        object.__setattr__(self, "token_symbol", symbol)
        object.__setattr__(self, "social_urls", urls)
        object.__setattr__(self, "transaction_hash", transaction_hash)
        object.__setattr__(self, "block_hash", block_hash)
        object.__setattr__(self, "factory_address", factory)
        object.__setattr__(self, "location_id", f"mint-location-{source}-{reference}")

def _optional_hash(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip().casefold()
    if not _HASH.fullmatch(result):
        raise ValueError("invalid BSC transaction or block hash")
    return result


def _text(value: object, limit: int) -> str | None:
    result = str(value or "").strip()
    return result[:limit] if result else None


def _urls(values: tuple[str, ...]) -> tuple[str, ...]:
    output = tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
    if len(output) > 16 or any(len(item) > 2_000 for item in output):
        raise ValueError("mint social URLs exceed their bounds")
    return output
