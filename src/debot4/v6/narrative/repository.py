"""Browser-free repository for immutable FxTwitter status observations."""

from __future__ import annotations

from datetime import datetime
from threading import Lock
from typing import Mapping

from .domain import TokenRef
from .fxtwitter import FxTwitterClient
from .leads import resolve_status_lead
from .models import ResearchOutcome, StatusResearch, aware_utc
from .protocols import StatusFetcher


class LiveNarrativeRepository:
    """Fetch exact status leads once per token and preserve first observation."""

    def __init__(self, fetcher: StatusFetcher | None = None) -> None:
        self._fetcher = fetcher or FxTwitterClient()
        self._cache: dict[tuple[str, str, str], StatusResearch] = {}
        self._lock = Lock()

    def research(
        self,
        token: TokenRef,
        token_context: Mapping[str, object] | object,
        *,
        lead_available_at: datetime,
    ) -> StatusResearch:
        available = aware_utc(lead_available_at, "lead_available_at")
        url, handle, status_id, identity, reason, integrity_error = (
            resolve_status_lead(token, token_context)
        )
        if url is None:
            return StatusResearch(
                token=token,
                outcome=(
                    ResearchOutcome.REJECT if integrity_error else ResearchOutcome.WAIT
                ),
                reason=reason,
                lead_identity=identity,
                lead_url=None,
                requested_handle=None,
                requested_status_id=None,
                lead_available_at=available,
            )
        key = (token.chain, token.address, url)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None:
                return cached
        result = self._fetch(
            token,
            url=url,
            handle=handle or "",
            status_id=status_id or "",
            lead_identity=identity,
            lead_available_at=available,
        )
        if result.outcome is not ResearchOutcome.FETCHED:
            return result
        with self._lock:
            return self._cache.setdefault(key, result)

    def _fetch(
        self,
        token: TokenRef,
        *,
        url: str,
        handle: str,
        status_id: str,
        lead_identity: str,
        lead_available_at: datetime,
    ) -> StatusResearch:
        try:
            tweet = self._fetcher.fetch_status(url)
        except Exception:
            return _result(
                token, ResearchOutcome.WAIT, "status_fetch_unavailable", lead_identity,
                url, handle, status_id, lead_available_at,
            )
        try:
            published = aware_utc(tweet.published_at, "tweet.published_at")
            fetched = aware_utc(tweet.fetched_at, "tweet.fetched_at")
        except (AttributeError, TypeError, ValueError):
            return _result(
                token, ResearchOutcome.REJECT, "status_schema_invalid", lead_identity,
                url, handle, status_id, lead_available_at,
            )
        if tweet.tweet_id != status_id or tweet.author_handle.casefold() != handle.casefold():
            return _result(
                token, ResearchOutcome.REJECT, "status_identity_mismatch", lead_identity,
                url, handle, status_id, lead_available_at,
            )
        if published > lead_available_at or lead_available_at > fetched:
            return _result(
                token, ResearchOutcome.REJECT, "status_time_order_invalid", lead_identity,
                url, handle, status_id, lead_available_at,
            )
        return StatusResearch(
            token=token,
            outcome=ResearchOutcome.FETCHED,
            reason="exact_status_fetched",
            lead_identity=lead_identity,
            lead_url=url,
            requested_handle=handle,
            requested_status_id=status_id,
            lead_available_at=lead_available_at,
            tweet=tweet,
        )


def _result(
    token: TokenRef,
    outcome: ResearchOutcome,
    reason: str,
    identity: str,
    url: str,
    handle: str,
    status_id: str,
    available: datetime,
) -> StatusResearch:
    return StatusResearch(
        token, outcome, reason, identity, url, handle, status_id, available
    )
