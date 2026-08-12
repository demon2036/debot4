"""Deterministic exact-CA X-search tasks built from verified market candidates."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from typing import Iterable

from .models import normalize_evm_address


UTC = timezone.utc


@dataclass(frozen=True, slots=True)
class XSearchSeed:
    address: str
    name: str
    symbol: str
    created_at: int
    peak_at: int
    window_start: int
    window_end_exclusive: int
    peak_fdv_usd: str
    max_kols: int

    def __post_init__(self) -> None:
        address = normalize_evm_address(self.address)
        if not self.window_start <= self.created_at < self.window_end_exclusive:
            raise ValueError("seed creation time is outside its fixed window")
        if not self.window_start <= self.peak_at < self.window_end_exclusive:
            raise ValueError("seed peak time is outside its fixed window")
        if self.max_kols < 0:
            raise ValueError("max_kols cannot be negative")
        object.__setattr__(self, "address", address)


@dataclass(frozen=True, slots=True)
class ExactCaXTask:
    key: str
    lane: str
    addresses: tuple[str, ...]
    prompt: str
    prompt_sha256: str


def exact_ca_x_tasks(
    seeds: Iterable[XSearchSeed], *, batch_size: int = 5,
) -> tuple[ExactCaXTask, ...]:
    """Ask two complementary searches for every CA without changing eligibility."""

    if not 1 <= batch_size <= 10:
        raise ValueError("batch_size must be between one and ten")
    groups: dict[tuple[int, int], list[XSearchSeed]] = {}
    for seed in seeds:
        groups.setdefault(
            (seed.window_start, seed.window_end_exclusive), [],
        ).append(seed)
    tasks = []
    for bounds in sorted(groups):
        ordered = sorted(groups[bounds], key=lambda item: (item.created_at, item.address))
        for offset in range(0, len(ordered), batch_size):
            batch = tuple(ordered[offset:offset + batch_size])
            digest = sha256("\n".join(item.address for item in batch).encode()).hexdigest()[:12]
            for lane in ("authored_posts", "identity_attribution"):
                prompt = _prompt(batch, lane)
                tasks.append(ExactCaXTask(
                    key=f"{bounds[0]}_{bounds[1]}:{digest}:{lane}",
                    lane=lane,
                    addresses=tuple(item.address for item in batch),
                    prompt=prompt,
                    prompt_sha256=sha256(prompt.encode()).hexdigest(),
                ))
    return tuple(tasks)


def _prompt(batch: tuple[XSearchSeed, ...], lane: str) -> str:
    start = _time(batch[0].window_start)
    end = _time(batch[0].window_end_exclusive)
    records = "\n".join(
        f"- CA={item.address}; name={item.name!r}; symbol={item.symbol!r}; "
        f"created={_time(item.created_at)}; peak={_time(item.peak_at)}; "
        f"peak_FDV≈${item.peak_fdv_usd}; DeBot_max_kols={item.max_kols}"
        for item in batch
    )
    if lane == "authored_posts":
        job = """
For EACH exact CA, carpet-search X for the earliest authored status containing that
literal address. Search Chinese aliases and English posts. Return direct x.com status
URLs, author handle/display name, post time, quoted text, and classify each occurrence
as own call, catalyst, project account, scanner, repost, market recap, or unclear.
Prioritize posts before the recorded peak, including calls several days before it.
""".strip()
    else:
        job = """
For EACH exact CA, find the X identities behind pre-peak calls and any DeBot/GMGN KOL
label. Resolve Chinese aliases, old/new handles, stable identity clues, attribution
pages, and optional wallets/buy transactions. A KOL can be real without a wallet.
An alleged shadow wallet may buy several days before a call; one such buy is only a candidate,
and repeated independent exact-CA hits are optional corroboration, never a requirement.
""".strip()
    return f"""
BSC fixed UTC window [{start}, {end}). These tokens were independently measured at
window peak MC/FDV >= $500,000; that fact does not prove a KOL bought or called them.

{records}

{job}

Do not infer a contract from ticker/name. Do not treat max_kols, a transfer, smart-money
tag, scanner post, or post-pump recap as a verified KOL buy/call. Give null for unknown,
include direct source URLs, state searches with no hit, and never claim completeness.
""".strip()


def _time(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, UTC).isoformat().replace("+00:00", "Z")
