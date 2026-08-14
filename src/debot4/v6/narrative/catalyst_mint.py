"""Deterministic evidence joining one reviewed X catalyst to one new BSC mint."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from ..debot.ranks_models import RankSnapshot
from ..identity import bsc_address, stable_id, utc_datetime
from ..x.models import XPost
from .fxtwitter import FxTwitterError, parse_x_status_url


MATCH_SCHEMA = "debot4.v6.catalyst-mint-match.v1"
MATCH_KIND = "exact_x_status_id"
MIN_MINT_DELAY = timedelta(seconds=-30)
MAX_MINT_DELAY = timedelta(minutes=10)


@dataclass(frozen=True, slots=True)
class CatalystMintMatch:
    """Exact metadata binding, never an endorsement, price cause, or buy signal."""

    exact_ca: str
    token_created_at: datetime
    observed_at: datetime
    token_name: str | None
    token_symbol: str | None
    provider_fdv_usd: Decimal | None
    launchpad: str | None
    token_description: str | None
    token_social_urls: tuple[str, ...]
    token_status_url: str
    catalyst_tweet_id: str
    catalyst_author: str
    catalyst_text: str
    catalyst_created_at: datetime
    catalyst_fetched_at: datetime
    match_id: str = field(init=False)
    match_kind: str = field(default=MATCH_KIND, init=False)
    authorizes_trade: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        exact_ca = bsc_address(self.exact_ca)
        token_created = utc_datetime(self.token_created_at)
        observed = utc_datetime(self.observed_at)
        catalyst_created = utc_datetime(self.catalyst_created_at)
        catalyst_fetched = utc_datetime(self.catalyst_fetched_at)
        author = self.catalyst_author.strip().lstrip("@").casefold()
        text = self.catalyst_text.strip()
        status_url = self.token_status_url.strip()
        try:
            _, status_id = parse_x_status_url(status_url)
            canonical_author, _ = parse_x_status_url(
                f"https://x.com/{author}/status/{self.catalyst_tweet_id}"
            )
        except FxTwitterError as exc:
            raise ValueError("invalid catalyst X identity") from exc
        delay = token_created - catalyst_created
        if status_id != self.catalyst_tweet_id:
            raise ValueError("token status URL does not bind the catalyst tweet")
        if not MIN_MINT_DELAY <= delay <= MAX_MINT_DELAY:
            raise ValueError("catalyst-to-mint delay is outside the match window")
        if observed < max(catalyst_fetched, token_created):
            raise ValueError("match observation predates its available evidence")
        if canonical_author.casefold() != author or not text or len(text) > 4_000:
            raise ValueError("invalid catalyst identity or content")
        fdv = self.provider_fdv_usd
        if fdv is not None and (not fdv.is_finite() or fdv < 0):
            raise ValueError("provider FDV must be finite and non-negative")
        urls = _urls(self.token_social_urls)
        if status_url not in urls:
            raise ValueError("matched status URL must be present in token metadata")
        object.__setattr__(self, "exact_ca", exact_ca)
        object.__setattr__(self, "token_created_at", token_created)
        object.__setattr__(self, "observed_at", observed)
        object.__setattr__(self, "catalyst_created_at", catalyst_created)
        object.__setattr__(self, "catalyst_fetched_at", catalyst_fetched)
        object.__setattr__(self, "catalyst_author", author)
        object.__setattr__(self, "catalyst_text", text)
        object.__setattr__(self, "token_name", _text(self.token_name, 160))
        object.__setattr__(self, "token_symbol", _text(self.token_symbol, 80))
        object.__setattr__(self, "launchpad", _text(self.launchpad, 80))
        object.__setattr__(
            self, "token_description", _text(self.token_description, 1_000)
        )
        object.__setattr__(self, "token_social_urls", urls)
        object.__setattr__(self, "token_status_url", status_url)
        object.__setattr__(
            self,
            "match_id",
            stable_id(
                "catalyst-mint",
                MATCH_SCHEMA,
                exact_ca,
                self.catalyst_tweet_id,
                token_created.isoformat(),
            ),
        )

    @property
    def catalyst_status_url(self) -> str:
        return f"https://x.com/{self.catalyst_author}/status/{self.catalyst_tweet_id}"

    @property
    def mint_delay_seconds(self) -> float:
        return (self.token_created_at - self.catalyst_created_at).total_seconds()

    @classmethod
    def from_observations(
        cls, post: XPost, snapshot: RankSnapshot,
    ) -> "CatalystMintMatch | None":
        if snapshot.created_at is None:
            return None
        status_url = _matching_url(snapshot.social_urls, post.tweet_id)
        if status_url is None:
            return None
        delay = utc_datetime(snapshot.created_at) - utc_datetime(post.created_at)
        if not MIN_MINT_DELAY <= delay <= MAX_MINT_DELAY:
            return None
        observed = max(utc_datetime(post.fetched_at), utc_datetime(snapshot.fetched_at))
        return cls(
            exact_ca=snapshot.token_address,
            token_created_at=snapshot.created_at,
            observed_at=observed,
            token_name=snapshot.name,
            token_symbol=snapshot.symbol,
            provider_fdv_usd=snapshot.provider_fdv_usd,
            launchpad=snapshot.launchpad,
            token_description=snapshot.description,
            token_social_urls=snapshot.social_urls,
            token_status_url=status_url,
            catalyst_tweet_id=post.tweet_id,
            catalyst_author=post.author,
            catalyst_text=post.text,
            catalyst_created_at=post.created_at,
            catalyst_fetched_at=post.fetched_at,
        )


def x_status_ids(urls: tuple[str, ...]) -> frozenset[str]:
    found: set[str] = set()
    for url in urls:
        try:
            found.add(parse_x_status_url(url)[1])
        except FxTwitterError:
            continue
    return frozenset(found)


def _matching_url(urls: tuple[str, ...], tweet_id: str) -> str | None:
    for url in urls:
        try:
            if parse_x_status_url(url)[1] == tweet_id:
                return url
        except FxTwitterError:
            continue
    return None


def _urls(values: tuple[str, ...]) -> tuple[str, ...]:
    output = tuple(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))
    if len(output) > 16 or any(len(item) > 2_000 for item in output):
        raise ValueError("token social URLs exceed their bounds")
    return output


def _text(value: object, limit: int) -> str | None:
    text = str(value or "").strip()
    return text[:limit] if text else None
