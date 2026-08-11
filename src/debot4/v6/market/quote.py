"""Same-block Pancake-v2 MC, paper fill, and liquidation calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from threading import Lock

from ..domain import ChainHead, ExecutionQuote, PairState, PositionMark
from ..identity import bsc_address
from . import evm
from .oracle import OracleError, UsdOracle
from .rpc import BscRpc, RpcError


getcontext().prec = 60
UTC = timezone.utc
FEE_BPS = 25
BPS = Decimal(10_000)


class MarketQuoteError(RuntimeError):
    """The pair is unsupported, stale, or could not be quoted safely."""


@dataclass(frozen=True, slots=True)
class _PairMeta:
    token_is_zero: bool
    quote_address: str
    token_decimals: int
    quote_decimals: int


class MarketQuoteEngine:
    def __init__(self, rpc: BscRpc) -> None:
        self.rpc = rpc
        self.oracle = UsdOracle(rpc)
        self._meta: dict[tuple[str, str], _PairMeta] = {}
        self._lock = Lock()

    def state(
        self,
        token_address: str,
        pair_address: str,
        *,
        head: ChainHead | None = None,
    ) -> PairState:
        token = bsc_address(token_address)
        pair = bsc_address(pair_address)
        head = head or self.rpc.head()
        meta = self._pair_meta(token, pair, head.number)
        calls = [evm.call(pair, evm.GET_RESERVES), evm.call(token, evm.TOTAL_SUPPLY)]
        try:
            values = self.rpc.eth_calls(calls, block_number=head.number)
            reserve0, reserve1, _ = evm.reserves(values[0])
            total_supply = evm.uint(values[1])
            quote_usd = self.oracle.price(meta.quote_address, head.number, head.timestamp)
        except (RpcError, ValueError, OracleError) as exc:
            raise MarketQuoteError("fixed-block pair state could not be read") from exc
        token_reserve, quote_reserve = (
            (reserve0, reserve1) if meta.token_is_zero else (reserve1, reserve0)
        )
        if token_reserve <= 0 or quote_reserve <= 0 or total_supply <= 0:
            raise MarketQuoteError("pair reserves or total supply are empty")
        return PairState(
            head=head,
            pair_address=pair,
            token_address=token,
            quote_address=meta.quote_address,
            token_is_zero=meta.token_is_zero,
            token_decimals=meta.token_decimals,
            quote_decimals=meta.quote_decimals,
            token_reserve_raw=token_reserve,
            quote_reserve_raw=quote_reserve,
            total_supply_raw=total_supply,
            quote_usd=quote_usd,
        )

    def buy_quote(
        self,
        token_address: str,
        pair_address: str,
        *,
        notional_usd: Decimal,
        buy_tax_pct: Decimal,
        sell_tax_pct: Decimal,
        head: ChainHead | None = None,
    ) -> ExecutionQuote:
        state = self.state(token_address, pair_address, head=head)
        spot_fdv, liquidity = _valuation(state)
        quote_in = int(
            notional_usd / state.quote_usd * (Decimal(10) ** state.quote_decimals)
        )
        if quote_in <= 0:
            raise MarketQuoteError("paper notional rounds to zero")
        raw_out = _amount_out(quote_in, state.quote_reserve_raw, state.token_reserve_raw)
        received = int(Decimal(raw_out) * (Decimal(100) - buy_tax_pct) / 100)
        if received <= 0:
            raise MarketQuoteError("paper buy receives no tokens")
        token_units = Decimal(received) / (Decimal(10) ** state.token_decimals)
        fill_price = notional_usd / token_units
        supply = Decimal(state.total_supply_raw) / (Decimal(10) ** state.token_decimals)
        fill_fdv = fill_price * supply
        spot_price = spot_fdv / supply
        impact = max(Decimal(0), (fill_price / spot_price - 1) * BPS)
        sell_input = int(Decimal(received) * (Decimal(100) - sell_tax_pct) / 100)
        immediate_raw = _amount_out(
            sell_input,
            state.token_reserve_raw - raw_out,
            state.quote_reserve_raw + quote_in,
        )
        immediate_usd = (
            Decimal(immediate_raw) / (Decimal(10) ** state.quote_decimals)
        ) * state.quote_usd
        return ExecutionQuote(
            state, notional_usd, buy_tax_pct, sell_tax_pct, spot_fdv, fill_fdv,
            liquidity, impact, received, immediate_usd,
        )

    def mark(
        self, token_address: str, pair_address: str, *,
        tokens_received_raw: int, sell_tax_pct: Decimal,
        head: ChainHead | None = None,
    ) -> PositionMark:
        state = self.state(token_address, pair_address, head=head)
        fdv, _ = _valuation(state)
        sell_input = int(
            Decimal(tokens_received_raw) * (Decimal(100) - sell_tax_pct) / 100
        )
        quote_out = _amount_out(
            sell_input, state.token_reserve_raw, state.quote_reserve_raw
        )
        exit_usd = (
            Decimal(quote_out) / (Decimal(10) ** state.quote_decimals)
        ) * state.quote_usd
        return PositionMark(state, fdv, exit_usd)

    def _pair_meta(self, token: str, pair: str, block_number: int) -> _PairMeta:
        key = (token, pair)
        with self._lock:
            cached = self._meta.get(key)
        if cached is not None:
            return cached
        try:
            token0_raw, token1_raw = self.rpc.eth_calls(
                [evm.call(pair, evm.TOKEN0), evm.call(pair, evm.TOKEN1)],
                block_number=block_number,
            )
            token0, token1 = evm.address(token0_raw), evm.address(token1_raw)
        except (RpcError, ValueError) as exc:
            raise MarketQuoteError("pair is not a supported v2 pool") from exc
        if token not in {token0, token1}:
            raise MarketQuoteError("pair does not contain the candidate token")
        quote = token1 if token == token0 else token0
        try:
            token_dec_raw, quote_dec_raw = self.rpc.eth_calls(
                [evm.call(token, evm.DECIMALS), evm.call(quote, evm.DECIMALS)],
                block_number=block_number,
            )
            token_decimals = evm.uint(token_dec_raw)
            quote_decimals = evm.uint(quote_dec_raw)
        except (RpcError, ValueError) as exc:
            raise MarketQuoteError("token decimals could not be read") from exc
        if token_decimals > 36 or quote_decimals > 36:
            raise MarketQuoteError("token decimals are invalid")
        result = _PairMeta(token == token0, quote, token_decimals, quote_decimals)
        with self._lock:
            self._meta[key] = result
        return result


def _valuation(state: PairState) -> tuple[Decimal, Decimal]:
    token_units = Decimal(state.token_reserve_raw) / (Decimal(10) ** state.token_decimals)
    quote_units = Decimal(state.quote_reserve_raw) / (Decimal(10) ** state.quote_decimals)
    token_price = quote_units * state.quote_usd / token_units
    supply = Decimal(state.total_supply_raw) / (Decimal(10) ** state.token_decimals)
    return token_price * supply, quote_units * state.quote_usd * 2


def _amount_out(amount_in: int, reserve_in: int, reserve_out: int) -> int:
    if amount_in <= 0 or reserve_in <= 0 or reserve_out <= 0:
        return 0
    fee_adjusted = amount_in * (10_000 - FEE_BPS)
    return fee_adjusted * reserve_out // (reserve_in * 10_000 + fee_adjusted)
