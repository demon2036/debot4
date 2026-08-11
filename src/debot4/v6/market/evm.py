"""Minimal ABI encoding and decoding needed by the v6 quote path."""

from __future__ import annotations

from typing import Iterable

from ..identity import bsc_address


TOKEN0 = "0x0dfe1681"
TOKEN1 = "0xd21220a7"
GET_RESERVES = "0x0902f1ac"
DECIMALS = "0x313ce567"
TOTAL_SUPPLY = "0x18160ddd"
LATEST_ROUND_DATA = "0xfeaf968c"
GET_PAIR = "0xe6a43905"


def call(to: str, data: str) -> dict[str, str]:
    return {"to": bsc_address(to), "data": _hex(data)}


def address_call(selector: str, *addresses: str) -> str:
    data = _payload(selector)
    if len(data) != 8:
        raise ValueError("function selector must be four bytes")
    for value in addresses:
        data += bsc_address(value)[2:].rjust(64, "0")
    return "0x" + data


def uint(value: str, word: int = 0) -> int:
    raw = bytes.fromhex(_payload(value))
    start = word * 32
    if len(raw) < start + 32:
        raise ValueError("ABI uint response is too short")
    return int.from_bytes(raw[start : start + 32], "big")


def signed(value: str, word: int = 0) -> int:
    raw = uint(value, word)
    return raw - (1 << 256) if raw >= 1 << 255 else raw


def address(value: str, word: int = 0) -> str:
    raw = bytes.fromhex(_payload(value))
    start = word * 32
    if len(raw) < start + 32:
        raise ValueError("ABI address response is too short")
    return bsc_address("0x" + raw[start + 12 : start + 32].hex())


def reserves(value: str) -> tuple[int, int, int]:
    return uint(value, 0), uint(value, 1), uint(value, 2)


def block_tag(number: int) -> str:
    if number < 0:
        raise ValueError("block number must be non-negative")
    return hex(number)


def results(values: Iterable[object]) -> tuple[str, ...]:
    parsed = []
    for value in values:
        if not isinstance(value, str):
            raise ValueError("eth_call result is not hex text")
        _payload(value)
        parsed.append(value)
    return tuple(parsed)


def _hex(value: str) -> str:
    payload = _payload(value)
    return "0x" + payload


def _payload(value: str) -> str:
    if not isinstance(value, str) or not value.startswith("0x"):
        raise ValueError("value is not hex text")
    payload = value[2:]
    if len(payload) % 2:
        raise ValueError("hex payload has odd length")
    try:
        bytes.fromhex(payload)
    except ValueError as exc:
        raise ValueError("value contains invalid hex") from exc
    return payload
