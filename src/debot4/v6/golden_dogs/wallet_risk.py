"""Authoritative provider-tag screen for wallet manipulation risk."""

from __future__ import annotations

from typing import Iterable


MANIPULATIVE_WALLET_TAGS = frozenset({
    "sandwich_bot",
    "sybil",
    "wash_trader",
})


def manipulative_wallet_tags(tags: Iterable[str]) -> tuple[str, ...]:
    """Return normalized provider tags that disqualify wallet evidence."""

    normalized = {str(tag).strip().casefold() for tag in tags if str(tag).strip()}
    return tuple(sorted(normalized & MANIPULATIVE_WALLET_TAGS))


def has_manipulative_wallet_tag(tags: Iterable[str]) -> bool:
    return bool(manipulative_wallet_tags(tags))
