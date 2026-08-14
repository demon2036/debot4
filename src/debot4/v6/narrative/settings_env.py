"""Environment value parsing and public defaults for narrative settings."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping


DEFAULT_BSC_RPC_ENDPOINTS = (
    "https://bsc.publicnode.com",
    "https://bsc-mainnet.public.blastapi.io",
    "https://bsc-dataseed.binance.org",
)


def number(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, str(default)))
    except ValueError:
        raise ValueError(f"{key} must be numeric") from None


def integer(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key, str(default))
    try:
        if any(char in value for char in ".eE"):
            raise ValueError
        return int(value)
    except ValueError:
        raise ValueError(f"{key} must be an integer") from None


def optional_path(value: str) -> Path | None:
    return Path(value.strip()) if value.strip() else None


def csv(value: str, default: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip()) or default
