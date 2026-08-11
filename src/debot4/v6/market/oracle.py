"""Same-block USD prices for WBNB, stables, and v2-routable quote tokens."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from threading import Lock

from ..identity import bsc_address
from . import evm
from .rpc import BscRpc, RpcError


FACTORY = "0xca143ce32fe78f1f7019d7d551a6402fc5350c73"
WBNB = "0xbb4cdb9cbd36b01bd1cbaebf2de08d9173bc095c"
USDT = "0x55d398326f99059ff775485246999027b3197955"
BNB_USD_FEED = "0x0567f2323251f0aab15c8dfb1967e4e8a7d42aee"
STABLES = {
    USDT,
    "0x8ac76a51cc950d9822d68b83fe1ad97b32cd580d",
    "0xe9e7cea3dedca5984780bafc599bd69add087d56",
}
ZERO = "0x0000000000000000000000000000000000000000"


class OracleError(RuntimeError):
    """No bounded same-block USD route exists for the quote asset."""


@dataclass(frozen=True, slots=True)
class _Route:
    pair: str
    base: str
    asset_is_zero: bool
    asset_decimals: int
    base_decimals: int


class UsdOracle:
    def __init__(self, rpc: BscRpc) -> None:
        self.rpc = rpc
        self._routes: dict[str, _Route] = {}
        self._lock = Lock()

    def price(self, asset: str, block_number: int, block_time: datetime) -> Decimal:
        token = bsc_address(asset)
        if token in STABLES:
            return Decimal(1)
        if token == WBNB:
            return self._bnb_price(block_number, block_time)
        route = self._route(token, block_number, block_time)
        base_usd = self.price(route.base, block_number, block_time)
        try:
            reserve_raw = self.rpc.eth_calls(
                [evm.call(route.pair, evm.GET_RESERVES)], block_number=block_number
            )[0]
            reserve0, reserve1, _ = evm.reserves(reserve_raw)
        except (RpcError, ValueError) as exc:
            raise OracleError("quote route reserves could not be read") from exc
        asset_raw, base_raw = (
            (reserve0, reserve1) if route.asset_is_zero else (reserve1, reserve0)
        )
        if asset_raw <= 0 or base_raw <= 0:
            raise OracleError("quote route reserves are empty")
        asset_units = Decimal(asset_raw) / (Decimal(10) ** route.asset_decimals)
        base_units = Decimal(base_raw) / (Decimal(10) ** route.base_decimals)
        return base_units * base_usd / asset_units

    def _bnb_price(self, block_number: int, block_time: datetime) -> Decimal:
        try:
            decimals_raw, round_raw = self.rpc.eth_calls(
                [
                    evm.call(BNB_USD_FEED, evm.DECIMALS),
                    evm.call(BNB_USD_FEED, evm.LATEST_ROUND_DATA),
                ],
                block_number=block_number,
            )
            decimals = evm.uint(decimals_raw)
            answer = evm.signed(round_raw, 1)
            updated_at = evm.uint(round_raw, 3)
        except (RpcError, ValueError) as exc:
            raise OracleError("BNB/USD feed could not be read") from exc
        if answer <= 0 or updated_at <= 0:
            raise OracleError("BNB/USD feed is invalid")
        if block_time.timestamp() - updated_at > 180:
            raise OracleError("BNB/USD feed is stale")
        return Decimal(answer) / (Decimal(10) ** decimals)

    def _route(self, asset: str, block_number: int, block_time: datetime) -> _Route:
        with self._lock:
            cached = self._routes.get(asset)
        if cached is not None:
            return cached
        candidates = self._discover(asset, block_number)
        ranked = []
        for route in candidates:
            try:
                reserve_raw = self.rpc.eth_calls(
                    [evm.call(route.pair, evm.GET_RESERVES)],
                    block_number=block_number,
                )[0]
                reserve0, reserve1, _ = evm.reserves(reserve_raw)
                base_raw = reserve1 if route.asset_is_zero else reserve0
                base_usd = self.price(route.base, block_number, block_time)
                depth = Decimal(base_raw) / (Decimal(10) ** route.base_decimals) * base_usd
            except (RpcError, ValueError, OracleError):
                continue
            if depth > 0:
                ranked.append((depth, route))
        if not ranked:
            raise OracleError("quote asset has no liquid v2 USD route")
        result = max(ranked, key=lambda item: item[0])[1]
        with self._lock:
            self._routes[asset] = result
        return result

    def _discover(self, asset: str, block_number: int) -> tuple[_Route, ...]:
        bases = (WBNB, USDT)
        calls = [
            evm.call(FACTORY, evm.address_call(evm.GET_PAIR, asset, base))
            for base in bases
        ]
        try:
            pair_values = self.rpc.eth_calls(calls, block_number=block_number)
            pairs = tuple(evm.address(value) for value in pair_values)
        except (RpcError, ValueError) as exc:
            raise OracleError("quote routes could not be discovered") from exc
        routes = []
        for pair, base in zip(pairs, bases):
            if pair == ZERO:
                continue
            try:
                token0_raw, token1_raw, asset_dec_raw, base_dec_raw = self.rpc.eth_calls(
                    [
                        evm.call(pair, evm.TOKEN0),
                        evm.call(pair, evm.TOKEN1),
                        evm.call(asset, evm.DECIMALS),
                        evm.call(base, evm.DECIMALS),
                    ],
                    block_number=block_number,
                )
                token0, token1 = evm.address(token0_raw), evm.address(token1_raw)
                asset_decimals, base_decimals = evm.uint(asset_dec_raw), evm.uint(base_dec_raw)
            except (RpcError, ValueError):
                continue
            if {token0, token1} != {asset, base} or max(asset_decimals, base_decimals) > 36:
                continue
            routes.append(_Route(pair, base, asset == token0, asset_decimals, base_decimals))
        return tuple(routes)
